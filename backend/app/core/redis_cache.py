import json
import hashlib
import unicodedata
import re
import time
import math
import logging
import threading
import os
import copy
import functools
from typing import List, Dict, Any, Optional, Tuple

try:
    from app.core.config import settings
except Exception:
    class SettingsFallback:
        UPSTASH_REDIS_URL: str = os.getenv("UPSTASH_REDIS_URL", "")
        REDIS_URL: str = os.getenv("REDIS_URL", "")
    settings = SettingsFallback()

logger = logging.getLogger(__name__)

# Optional redis-py import with safe degradation
try:
    import redis
except ImportError:
    redis = None


def normalize_text(text: str) -> str:
    """
    Normalizes query text by removing accents, diacritics, punctuation
    (including Spanish inverted marks, smart quotes, guillemets, dashes),
    and extra whitespace, converting to lowercase.
    Ensures that queries differing only by casing, accents, quotation marks,
    or whitespace produce identical hashes.
    
    Example: '¿Requisitos para PASANTÍA?!' -> 'requisitos para pasantia'
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    lowered = stripped.lower()
    # Strip any Unicode punctuation (Po, Pi, Pf, Pd, Ps, Pe, Pc)
    cleaned = "".join(" " if unicodedata.category(c).startswith("P") else c for c in lowered)
    return " ".join(cleaned.split())


def compute_query_hash(query: str) -> str:
    """Computes SHA-256 hash of normalized query string for Layer 1 exact lookup."""
    norm = normalize_text(query)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Computes cosine similarity between two float vectors.
    Returns 0.0 if vectors are empty or norm is zero.
    """
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(b * b for b in v2))
    if norm_v1 == 0.0 or norm_v2 == 0.0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)


@functools.lru_cache(maxsize=1024)
def _cached_embedding_tuple(normalized_text: str) -> Tuple[float, ...]:
    """Internal LRU-cached embedding computation on normalized text."""
    try:
        from app.services.rag_service import rag_service
        emb = rag_service.embed_query(normalized_text)
        if emb:
            return tuple(emb)
    except Exception as e:
        logger.debug(f"[RedisCache] RAG embed_query fallback to llm_adapter: {e}")
    try:
        from app.services.llm_adapter import llm_adapter
        emb = llm_adapter.get_embeddings([normalized_text])[0]
        return tuple(emb) if emb else ()
    except Exception as err:
        logger.debug(f"[RedisCache] LLM adapter embedding failed ({err}), using local hash embedding fallback.")

    # Pure Python deterministic 384-d embedding fallback (ensures cache functions anywhere)
    dim = 384
    vec = [0.0] * dim
    for i, word in enumerate(normalized_text.split()):
        h = int(hashlib.md5(f"{word}_{i % 10}".encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return tuple(x / norm for x in vec)


def get_query_embedding(query: str) -> List[float]:
    """Generates query embedding using rag_service or llm_adapter fallback with LRU caching."""
    if not query or not query.strip():
        return []
    norm = normalize_text(query)
    emb_tuple = _cached_embedding_tuple(norm)
    return list(emb_tuple)


class InMemoryCache:
    """
    Thread-safe in-memory cache with TTL and LRU eviction.
    Serves as the high-speed local L1 layer and transparent fallback
    when Redis is unconfigured or unavailable.
    """

    def __init__(self, max_entries: int = 2000, default_ttl: int = 86400):
        self._lock = threading.RLock()
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._max_entries = max_entries
        self._default_ttl = default_ttl

    def _prune_expired(self):
        """Removes expired entries from memory."""
        now = time.time()
        expired_keys = [k for k, v in self._entries.items() if now > v.get("expires_at", 0)]
        for k in expired_keys:
            del self._entries[k]

    def get_exact(self, query_hash: str) -> Optional[Dict[str, Any]]:
        """Layer 1: Exact match O(1) lookup in memory."""
        with self._lock:
            entry = self._entries.get(query_hash)
            if not entry:
                return None
            if time.time() > entry.get("expires_at", 0):
                del self._entries[query_hash]
                return None
            entry["last_accessed"] = time.time()
            return copy.deepcopy(entry["payload"])

    def find_semantic(
        self,
        query_embedding: List[float],
        threshold: float = 0.95
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Layer 2: Scans in-memory embeddings for cosine similarity >= threshold.
        Returns (payload, similarity) or None.
        """
        if not query_embedding:
            return None

        with self._lock:
            now = time.time()
            best_entry = None
            best_sim = -1.0
            expired_keys = []

            for k, entry in self._entries.items():
                if now > entry.get("expires_at", 0):
                    expired_keys.append(k)
                    continue

                cached_emb = entry.get("embedding")
                if not cached_emb:
                    continue

                sim = cosine_similarity(query_embedding, cached_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_entry = entry

            for k in expired_keys:
                if k in self._entries:
                    del self._entries[k]

            if best_entry and best_sim >= threshold:
                best_entry["last_accessed"] = now
                return copy.deepcopy(best_entry["payload"]), best_sim

            return None

    def set(
        self,
        query_hash: str,
        query: str,
        payload: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        ttl: Optional[int] = None
    ):
        """Stores entry with TTL and manages capacity."""
        ttl_seconds = ttl if (ttl is not None and ttl > 0) else self._default_ttl
        with self._lock:
            if len(self._entries) >= self._max_entries:
                self._prune_expired()
                if len(self._entries) >= self._max_entries:
                    # LRU eviction: remove entry with oldest last_accessed
                    oldest_key = min(
                        self._entries.keys(),
                        key=lambda k: self._entries[k].get("last_accessed", 0)
                    )
                    del self._entries[oldest_key]

            self._entries[query_hash] = {
                "hash": query_hash,
                "query": query,
                "payload": copy.deepcopy(payload),
                "embedding": embedding or [],
                "expires_at": time.time() + ttl_seconds,
                "last_accessed": time.time()
            }

    def delete(self, query_hash: str):
        with self._lock:
            if query_hash in self._entries:
                del self._entries[query_hash]

    def invalidate_all(self):
        with self._lock:
            self._entries.clear()

    def size(self) -> int:
        with self._lock:
            self._prune_expired()
            return len(self._entries)

    def has_semantic_entries(self) -> bool:
        """Returns True if there is at least one active non-expired entry with an embedding."""
        with self._lock:
            now = time.time()
            return any(now <= v.get("expires_at", 0) and bool(v.get("embedding")) for v in self._entries.values())


class HybridRedisCache:
    """
    Hybrid Caching System for CanIGraduateUD-RAG:
    - Layer 1: Exact match on normalized text (SHA-256 hash), O(1), 0 latency, 0 tokens.
    - Layer 2: Semantic cache using cosine similarity on query embeddings (>= 0.95).
    - Transparent fallback to thread-safe in-memory RAM cache if Redis is unconfigured or unreachable.
    - Automatic TTL expiration and invalidation support.
    """

    KEY_PREFIX = "canigraduate:cache:"
    PAYLOAD_PREFIX = "canigraduate:cache:payload:"
    SEMANTIC_INDEX_KEY = "canigraduate:cache:semantic_index"

    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: int = 86400,
        semantic_threshold: float = 0.95
    ):
        self.default_ttl = default_ttl
        self.semantic_threshold = semantic_threshold
        self.ram_cache = InMemoryCache(max_entries=2000, default_ttl=default_ttl)

        # Determine Redis URL: explicit argument takes precedence (even if empty string)
        if redis_url is not None:
            self.redis_url = redis_url.strip()
        else:
            self.redis_url = (
                getattr(settings, "UPSTASH_REDIS_URL", "")
                or getattr(settings, "REDIS_URL", "")
                or ""
            ).strip()

        self.client = None
        self.redis_enabled = False
        self._stats_lock = threading.Lock()
        self.stats = {
            "exact_hits": 0,
            "semantic_hits": 0,
            "misses": 0,
            "writes": 0
        }

        self._init_redis()

    def _init_redis(self):
        """Initializes Redis client with graceful fallback on failure."""
        if not self.redis_url or redis is None:
            self.redis_enabled = False
            self.client = None
            return

        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0
            )
            self.client.ping()
            self.redis_enabled = True
            logger.info("[RedisCache] Successfully connected to Redis / Upstash instance.")
        except Exception as e:
            logger.warning(f"[RedisCache] Unable to connect to Redis at '{self.redis_url}' ({e}). Falling back to RAM cache.")
            self.client = None
            self.redis_enabled = False

    def is_redis_available(self) -> bool:
        """Returns True if Redis is configured and responding to ping."""
        if not self.redis_enabled or not self.client:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def _record_stat(self, metric: str):
        with self._stats_lock:
            self.stats[metric] = self.stats.get(metric, 0) + 1

    def get(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        similarity_threshold: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached response using two-tier hybrid strategy:
        1. Layer 1: Exact match on normalized text hash (O(1)).
        2. Layer 2: Semantic match on cosine similarity (>= 0.95).
        Returns dict with payload fields and cache metadata, or None.
        """
        if not query or not query.strip():
            return None

        threshold = similarity_threshold if similarity_threshold is not None else self.semantic_threshold
        query_hash = compute_query_hash(query)

        # -------------------------------------------------------------
        # LAYER 1: Exact Match (RAM -> Redis)
        # -------------------------------------------------------------
        # Check RAM first (0 latency)
        ram_hit = self.ram_cache.get_exact(query_hash)
        if ram_hit:
            self._record_stat("exact_hits")
            return {
                **ram_hit,
                "cache_hit": True,
                "cache_layer": "exact",
                "similarity": 1.0
            }

        # Check Redis if enabled
        if self.redis_enabled and self.client:
            try:
                raw_payload = self.client.get(f"{self.PAYLOAD_PREFIX}{query_hash}")
                if raw_payload:
                    payload = json.loads(raw_payload)
                    # Warm local RAM cache
                    self.ram_cache.set(
                        query_hash,
                        query,
                        payload,
                        embedding=payload.get("embedding", []),
                        ttl=self.default_ttl
                    )
                    self._record_stat("exact_hits")
                    return {
                        **payload,
                        "cache_hit": True,
                        "cache_layer": "exact",
                        "similarity": 1.0
                    }
            except Exception as e:
                logger.warning(f"[RedisCache] Layer 1 Redis lookup failed ({e}), continuing with RAM...")

        # -------------------------------------------------------------
        # LAYER 2: Semantic Match (RAM -> Redis)
        # -------------------------------------------------------------
        # Only compute embedding if at least one layer has semantic entries to compare
        has_ram_semantic = self.ram_cache.has_semantic_entries()
        has_redis_semantic = bool(self.redis_enabled and self.client)
        if not has_ram_semantic and not has_redis_semantic:
            self._record_stat("misses")
            return None

        embedding = query_embedding
        if embedding is None:
            embedding = get_query_embedding(query)

        if embedding:
            # Check RAM semantic match
            semantic_ram_hit = self.ram_cache.find_semantic(embedding, threshold=threshold)
            if semantic_ram_hit:
                payload, sim = semantic_ram_hit
                self._record_stat("semantic_hits")
                return {
                    **payload,
                    "cache_hit": True,
                    "cache_layer": "semantic",
                    "similarity": sim
                }

            # Check Redis semantic index if enabled
            if self.redis_enabled and self.client:
                try:
                    redis_semantic_hit = self._redis_find_semantic(embedding, threshold=threshold)
                    if redis_semantic_hit:
                        payload, sim = redis_semantic_hit
                        # Warm local RAM
                        p_hash = compute_query_hash(payload.get("query", query))
                        self.ram_cache.set(
                            p_hash,
                            payload.get("query", query),
                            payload,
                            embedding=payload.get("embedding", []) or embedding,
                            ttl=self.default_ttl
                        )
                        self._record_stat("semantic_hits")
                        return {
                            **payload,
                            "cache_hit": True,
                            "cache_layer": "semantic",
                            "similarity": sim
                        }
                except Exception as e:
                    logger.warning(f"[RedisCache] Layer 2 Redis lookup failed ({e}), continuing...")

        self._record_stat("misses")
        return None

    def _redis_find_semantic(
        self,
        query_embedding: List[float],
        threshold: float
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """Scans Redis semantic index for candidate with cosine similarity >= threshold."""
        try:
            all_entries = self.client.hgetall(self.SEMANTIC_INDEX_KEY)
        except Exception as e:
            logger.warning(f"[RedisCache] Failed to read semantic index from Redis: {e}")
            return None

        if not all_entries:
            return None

        now = time.time()
        best_hash = None
        best_sim = -1.0
        expired_hashes = []

        for q_hash, raw_meta in all_entries.items():
            try:
                meta = json.loads(raw_meta)
                if now > meta.get("expires_at", 0):
                    expired_hashes.append(q_hash)
                    continue

                cached_emb = meta.get("embedding")
                if not cached_emb:
                    continue

                sim = cosine_similarity(query_embedding, cached_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_hash = q_hash
            except Exception:
                continue

        # Clean expired keys in batch
        if expired_hashes:
            try:
                self.client.hdel(self.SEMANTIC_INDEX_KEY, *expired_hashes)
            except Exception:
                pass

        if best_hash and best_sim >= threshold:
            try:
                raw_payload = self.client.get(f"{self.PAYLOAD_PREFIX}{best_hash}")
                if raw_payload:
                    return json.loads(raw_payload), best_sim
            except Exception as e:
                logger.warning(f"[RedisCache] Failed to read payload for hash {best_hash}: {e}")

        return None

    def set(
        self,
        query: str,
        answer: str,
        citations: List[Dict[str, Any]],
        topic: str,
        embedding: Optional[List[float]] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Stores query answer, citations, and metadata in RAM and Redis.
        Payload format:
        {
            'query': query,
            'answer': answer,
            'citations': citations,
            'topic': topic,
            'timestamp': timestamp,
            'embedding': embedding
        }
        """
        if not query or not query.strip() or not answer or not answer.strip():
            return False

        effective_ttl = ttl if (ttl is not None and ttl > 0) else self.default_ttl
        query_hash = compute_query_hash(query)

        emb = embedding
        if emb is None:
            emb = get_query_embedding(query)

        payload = {
            "query": query,
            "answer": answer,
            "citations": citations or [],
            "topic": topic or "Normativa General",
            "timestamp": time.time(),
            "embedding": emb or []
        }

        # 1. Store in RAM cache (always succeeds)
        self.ram_cache.set(
            query_hash=query_hash,
            query=query,
            payload=payload,
            embedding=emb,
            ttl=effective_ttl
        )

        # 2. Store in Redis if enabled
        if self.redis_enabled and self.client:
            try:
                # Store exact payload
                self.client.setex(
                    f"{self.PAYLOAD_PREFIX}{query_hash}",
                    effective_ttl,
                    json.dumps(payload, ensure_ascii=False)
                )

                # Update semantic index
                index_item = {
                    "query": query,
                    "embedding": emb or [],
                    "expires_at": time.time() + effective_ttl
                }
                self.client.hset(
                    self.SEMANTIC_INDEX_KEY,
                    query_hash,
                    json.dumps(index_item, ensure_ascii=False)
                )
                # Keep hash index alive with overall expiry
                self.client.expire(self.SEMANTIC_INDEX_KEY, effective_ttl * 2)
            except Exception as e:
                logger.warning(f"[RedisCache] Failed to write to Redis ({e}), cached in RAM only.")

        self._record_stat("writes")
        return True

    def delete(self, query: str):
        """Invalidates a specific query from RAM and Redis."""
        query_hash = compute_query_hash(query)
        self.ram_cache.delete(query_hash)

        if self.redis_enabled and self.client:
            try:
                self.client.delete(f"{self.PAYLOAD_PREFIX}{query_hash}")
                self.client.hdel(self.SEMANTIC_INDEX_KEY, query_hash)
            except Exception as e:
                logger.warning(f"[RedisCache] Failed to delete key from Redis ({e})")

    def invalidate_all(self):
        """Flushes all cached entries from RAM and Redis."""
        self.ram_cache.invalidate_all()
        # Also clear local embedding LRU cache
        _cached_embedding_tuple.cache_clear()

        if self.redis_enabled and self.client:
            try:
                # Non-blocking scan and delete
                keys = list(self.client.scan_iter(f"{self.KEY_PREFIX}*", count=100))
                if keys:
                    self.client.delete(*keys)
                logger.info("[RedisCache] Invalidation complete. Flushed all cached keys.")
            except Exception as e:
                logger.warning(f"[RedisCache] Failed to invalidate Redis keys ({e})")

    def get_stats(self) -> Dict[str, Any]:
        """Returns operational metrics and health status."""
        with self._stats_lock:
            s = copy.deepcopy(self.stats)
        s["ram_entries"] = self.ram_cache.size()
        s["redis_available"] = self.is_redis_available()
        s["redis_enabled"] = self.redis_enabled
        return s


# Global singleton instance
redis_cache = HybridRedisCache()


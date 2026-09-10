import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import text, func
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.db.models import DocumentChunk, DocumentItem
from app.services.llm_adapter import llm_adapter

logger = logging.getLogger(__name__)


def _cosine_distance(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculates cosine distance (1 - cosine_similarity) between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 1.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 1.0
    sim = dot / ((norm_a ** 0.5) * (norm_b ** 0.5))
    sim = max(-1.0, min(1.0, sim))
    return 1.0 - sim


class VectorStoreService:
    """
    Stateless Vector Store Service powered by PostgreSQL pgvector (HNSW cosine similarity).
    Includes a transparent SQLite fallback with mathematical cosine distance for local pytest environments.
    """
    COLLECTION_NAME = "ud_sistemas_regulations"

    def __init__(self):
        self._is_postgres = engine.dialect.name == "postgresql"
        logger.info(f"VectorStoreService initialized (Engine: {engine.dialect.name}, pgvector: {self._is_postgres})")

    @property
    def is_postgres(self) -> bool:
        return engine.dialect.name == "postgresql"

    def add_chunks(
        self,
        chunks: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ):
        """Adds or updates text chunks with embeddings and metadata in the database."""
        if not chunks:
            return

        embeddings = llm_adapter.get_embeddings(chunks)
        db = SessionLocal()
        try:
            for i, chunk_text in enumerate(chunks):
                chunk_id = str(ids[i]) if ids and i < len(ids) else f"chunk_{i}"
                meta = metadatas[i] if metadatas and i < len(metadatas) else {}
                emb = embeddings[i] if embeddings and i < len(embeddings) else [0.0] * 1536

                doc_id = meta.get("document_id")
                if doc_id is not None:
                    try:
                        doc_id = int(doc_id)
                    except (ValueError, TypeError):
                        doc_id = None

                article = meta.get("article")
                chunk_idx = meta.get("chunk_index", i)

                existing = db.query(DocumentChunk).filter(DocumentChunk.chunk_id == chunk_id).first()
                if existing:
                    existing.content = chunk_text
                    existing.article = str(article) if article else None
                    existing.chunk_index = int(chunk_idx) if chunk_idx is not None else 0
                    existing.extra_metadata = json.dumps(meta, ensure_ascii=False)
                    existing.embedding = emb
                    if doc_id is not None:
                        existing.document_id = doc_id
                else:
                    new_chunk = DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        chunk_index=int(chunk_idx) if chunk_idx is not None else 0,
                        article=str(article) if article else None,
                        content=chunk_text,
                        extra_metadata=json.dumps(meta, ensure_ascii=False),
                        embedding=emb
                    )
                    db.add(new_chunk)

            db.commit()
            logger.info(f"Upserted {len(chunks)} chunks into vector store (Engine: {engine.dialect.name})")
        except Exception as e:
            db.rollback()
            logger.error(f"Error upserting chunks into vector store: {e}")
            raise e
        finally:
            db.close()

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        filter_criteria: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Queries the vector collection for relevant chunks ordered by cosine similarity.
        On PostgreSQL: Uses native pgvector <=> operator with HNSW index.
        On SQLite: Uses in-memory cosine distance for testing.
        """
        embeddings = llm_adapter.get_embeddings([query_text])
        query_embedding = embeddings[0] if embeddings else [0.0] * 1536

        db = SessionLocal()
        try:
            if self.is_postgres:
                return self._query_postgres(db, query_embedding, n_results, filter_criteria)
            else:
                return self._query_sqlite_fallback(db, query_embedding, n_results, filter_criteria)
        finally:
            db.close()

    def _query_postgres(
        self,
        db,
        query_embedding: List[float],
        n_results: int,
        filter_criteria: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Native PostgreSQL pgvector cosine distance query (<=>)."""
        vec_str = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"
        where_clauses = []
        params: Dict[str, Any] = {"qvec": vec_str, "limit": max(1, n_results)}

        if filter_criteria:
            if "document_id" in filter_criteria:
                where_clauses.append("document_id = :doc_id")
                params["doc_id"] = int(filter_criteria["document_id"])
            if "article" in filter_criteria:
                where_clauses.append("article = :article")
                params["article"] = str(filter_criteria["article"])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql = f"""
            SELECT chunk_id, document_id, article, content, extra_metadata,
                   (embedding <=> CAST(:qvec AS vector)) AS distance
            FROM document_chunks
            {where_sql}
            ORDER BY distance ASC
            LIMIT :limit;
        """

        rows = db.execute(text(sql), params).fetchall()
        results = []
        for r in rows:
            meta = {}
            if r[4]:
                try:
                    meta = json.loads(r[4])
                except Exception:
                    pass
            meta.setdefault("document_id", r[1])
            meta.setdefault("article", r[2])

            results.append({
                "id": str(r[0]),
                "content": str(r[3]),
                "metadata": meta,
                "distance": float(r[5])
            })
        return results

    def _query_sqlite_fallback(
        self,
        db,
        query_embedding: List[float],
        n_results: int,
        filter_criteria: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """In-memory cosine similarity query for SQLite / local testing."""
        query_builder = db.query(DocumentChunk)
        if filter_criteria:
            if "document_id" in filter_criteria:
                query_builder = query_builder.filter(DocumentChunk.document_id == int(filter_criteria["document_id"]))
            if "article" in filter_criteria:
                query_builder = query_builder.filter(DocumentChunk.article == str(filter_criteria["article"]))

        chunks = query_builder.all()
        scored_chunks = []

        for ch in chunks:
            ch_emb = ch.embedding
            if isinstance(ch_emb, str):
                try:
                    ch_emb = json.loads(ch_emb)
                except Exception:
                    ch_emb = []

            dist = _cosine_distance(query_embedding, ch_emb)
            meta = {}
            if ch.extra_metadata:
                try:
                    meta = json.loads(ch.extra_metadata)
                except Exception:
                    pass
            meta.setdefault("document_id", ch.document_id)
            meta.setdefault("article", ch.article)

            scored_chunks.append({
                "id": ch.chunk_id,
                "content": ch.content,
                "metadata": meta,
                "distance": dist
            })

        scored_chunks.sort(key=lambda x: x["distance"])
        return scored_chunks[:max(1, n_results)]

    def get_chunks_by_document_id(self, document_id: int) -> List[Dict[str, Any]]:
        """Retrieves all indexed chunks for a given document_id."""
        db = SessionLocal()
        try:
            chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index.asc()).all()
            formatted = []
            for ch in chunks:
                meta = {}
                if ch.extra_metadata:
                    try:
                        meta = json.loads(ch.extra_metadata)
                    except Exception:
                        pass
                meta.setdefault("document_id", ch.document_id)
                meta.setdefault("article", ch.article)
                formatted.append({
                    "id": ch.chunk_id,
                    "content": ch.content,
                    "metadata": meta
                })
            return formatted
        except Exception as e:
            logger.warning(f"Error fetching chunks for document_id {document_id}: {e}")
            return []
        finally:
            db.close()

    def delete_chunks_by_article(self, document_id: int, articles: List[str]) -> List[str]:
        """
        Selectively purges only the chunks matching specific articles/sections
        from a document in PostgreSQL/SQLite.
        """
        if not articles:
            return []

        chunks = self.get_chunks_by_document_id(document_id)
        ids_to_delete = []

        article_patterns = []
        for art in articles:
            clean_art = art.strip()
            num_match = re.search(r'\b(?:art[íi]culo|art\.?)\s*(\d+)', clean_art, re.IGNORECASE)
            if num_match:
                art_num = num_match.group(1)
                article_patterns.append(re.compile(rf'\b(?:art[íi]culo|art\.?)\s*{art_num}\b', re.IGNORECASE))
            else:
                article_patterns.append(re.compile(re.escape(clean_art), re.IGNORECASE))

        for ch in chunks:
            ch_id = ch["id"]
            meta_article = str(ch.get("metadata", {}).get("article", ""))
            content = str(ch.get("content", ""))

            matches = False
            for pat in article_patterns:
                if pat.search(meta_article) or pat.search(content):
                    matches = True
                    break

            if matches:
                ids_to_delete.append(ch_id)

        if ids_to_delete:
            db = SessionLocal()
            try:
                db.query(DocumentChunk).filter(DocumentChunk.chunk_id.in_(ids_to_delete)).delete(synchronize_session=False)
                db.commit()
                logger.info(f"Purged {len(ids_to_delete)} obsolete chunks for document_id {document_id}: {ids_to_delete}")
            except Exception as e:
                db.rollback()
                logger.error(f"Error purging chunks by article: {e}")
            finally:
                db.close()

        return ids_to_delete

    def delete_by_document_id(self, document_id: int):
        """Deletes all chunks belonging to a document_id."""
        db = SessionLocal()
        try:
            db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete(synchronize_session=False)
            db.commit()
            logger.info(f"Deleted chunks for document_id {document_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting chunks for document_id {document_id}: {e}")
        finally:
            db.close()

    def get_total_chunks(self) -> int:
        """Returns total number of chunks currently stored."""
        db = SessionLocal()
        try:
            return db.query(func.count(DocumentChunk.id)).scalar() or 0
        except Exception as e:
            logger.warning(f"Error getting total chunks: {e}")
            return 0
        finally:
            db.close()

    def reset(self):
        """Truncates all stored chunks."""
        db = SessionLocal()
        try:
            db.query(DocumentChunk).delete(synchronize_session=False)
            db.commit()
            logger.info("Reset vector store table.")
        except Exception as e:
            db.rollback()
            logger.error(f"Error resetting vector store: {e}")
        finally:
            db.close()


vector_store = VectorStoreService()


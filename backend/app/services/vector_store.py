import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from app.services.llm_adapter import llm_adapter

logger = logging.getLogger(__name__)

class VectorStoreService:
    COLLECTION_NAME = "ud_sistemas_regulations"

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIRECTORY,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "Normativas y comunicados de grado Ingeniería de Sistemas UD"}
        )

    def add_chunks(
        self,
        chunks: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ):
        """Adds text chunks with embeddings and metadata to ChromaDB."""
        if not chunks:
            return
        
        embeddings = llm_adapter.get_embeddings(chunks)
        try:
            self.collection.upsert(
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Upserted {len(chunks)} chunks into ChromaDB collection {self.COLLECTION_NAME}")
        except Exception as e:
            if "dimension" in str(e).lower():
                logger.warning(f"Dimension mismatch detected in ChromaDB: {e}. Resetting collection with new embedding dimensions...")
                self._reset_and_reseed(chunks, embeddings, metadatas, ids)
            else:
                raise e

    def _reset_and_reseed(self, chunks, embeddings, metadatas, ids):
        """Recreates collection with new dimensions and re-seeds base documents."""
        try:
            self.client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.client.create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "Normativas y comunicados de grado Ingeniería de Sistemas UD"}
        )
        self.collection.upsert(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Recreated collection and upserted {len(chunks)} chunks.")
        try:
            from app.scripts.seed_db import seed_knowledge_base
            seed_knowledge_base()
        except Exception as re_err:
            logger.warning(f"Reseed warning: {re_err}")

    def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Queries the vector collection for relevant chunks."""
        query_embedding = llm_adapter.get_embeddings([query_text])[0]
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, max(1, self.collection.count()))
            )
        except Exception as e:
            if "dimension" in str(e).lower():
                logger.warning(f"Dimension mismatch in query: {e}. Resetting collection...")
                self._reset_and_reseed([], [], [], [])
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(n_results, max(1, self.collection.count()))
                )
            else:
                raise e

        formatted_results = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
            distances = results["distances"][0] if "distances" in results else [0.0] * len(docs)
            ids = results["ids"][0] if "ids" in results else [""] * len(docs)

            for i in range(len(docs)):
                formatted_results.append({
                    "id": ids[i],
                    "content": docs[i],
                    "metadata": metas[i],
                    "distance": distances[i]
                })

        return formatted_results

    def delete_by_document_id(self, document_id: int):
        """Deletes all chunks belonging to a document_id."""
        self.collection.delete(
            where={"document_id": document_id}
        )
        logger.info(f"Deleted chunks for document_id {document_id}")

    def get_total_chunks(self) -> int:
        return self.collection.count()

vector_store = VectorStoreService()


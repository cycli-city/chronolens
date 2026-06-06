import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict, Optional
from datetime import datetime
import uuid


class TemporalVectorStore:
    """
    Vector store with temporal AND tenant awareness.
    Every chunk carries user_id metadata; every query filters by it.
    """

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self.embedder = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="chronolens_documents",
            embedding_function=self.embedder,
            metadata={"hnsw:space": "cosine"}
        )

    def _build_filter(self, conditions: list):
        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def add_document_version(
        self,
        user_id: str,
        document_id: str,
        version: int,
        timestamp: str,
        chunks: List[Dict],
        doc_name: str,
        doc_type: str = "general"
    ) -> List[str]:
        if not chunks:
            return []

        texts = [chunk["text"] for chunk in chunks]
        ids = []
        metadatas = []

        for chunk in chunks:
            chunk_id = f"{user_id[:8]}_{document_id}_v{version}_c{chunk['chunk_index']}_{uuid.uuid4().hex[:6]}"
            ids.append(chunk_id)
            metadatas.append({
                "user_id": user_id,
                "document_id": document_id,
                "version": version,
                "timestamp": timestamp,
                "doc_name": doc_name,
                "doc_type": doc_type,
                "chunk_index": chunk["chunk_index"],
                "added_at": datetime.utcnow().isoformat()
            })

        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
        return ids

    def query(
        self,
        user_id: str,
        query_text: str,
        n_results: int = 5,
        document_id: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Dict:
        conditions = [{"user_id": {"$eq": user_id}}]
        if document_id:
            conditions.append({"document_id": {"$eq": document_id}})
        if version is not None:
            conditions.append({"version": {"$eq": version}})

        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=self._build_filter(conditions)
        )
        return results

    def get_all_versions(self, user_id: str, document_id: str) -> List[Dict]:
        results = self.collection.get(
            where=self._build_filter([
                {"user_id": {"$eq": user_id}},
                {"document_id": {"$eq": document_id}},
            ])
        )

        versions = {}
        for meta in results.get("metadatas", []):
            v = meta["version"]
            if v not in versions:
                versions[v] = {
                    "version": v,
                    "timestamp": meta["timestamp"],
                    "doc_name": meta["doc_name"]
                }
        return sorted(versions.values(), key=lambda x: x["version"])

    def list_user_documents(self, user_id: str) -> List[str]:
        """Return all unique document IDs owned by this user."""
        results = self.collection.get(where={"user_id": {"$eq": user_id}})
        doc_ids = set()
        for meta in results.get("metadatas", []):
            doc_ids.add(meta["document_id"])
        return sorted(doc_ids)

    def get_version_chunks(self, user_id: str, document_id: str, version: int) -> List[Dict]:
        results = self.collection.get(
            where=self._build_filter([
                {"user_id": {"$eq": user_id}},
                {"document_id": {"$eq": document_id}},
                {"version": {"$eq": version}},
            ]),
            include=["documents", "metadatas", "embeddings"]
        )

        docs = results.get("documents") or []
        metas = results.get("metadatas") or []
        embs = results.get("embeddings")
        if embs is None:
            embs = []

        chunks = []
        for i in range(len(docs)):
            chunks.append({
                "text": docs[i],
                "chunk_index": metas[i].get("chunk_index", i),
                "embedding": embs[i] if i < len(embs) else None,
            })
        chunks.sort(key=lambda c: c["chunk_index"] if c["chunk_index"] is not None else 0)
        return chunks

    def count(self, user_id: Optional[str] = None) -> int:
        if user_id:
            results = self.collection.get(where={"user_id": {"$eq": user_id}})
            return len(results.get("ids", []))
        return self.collection.count()
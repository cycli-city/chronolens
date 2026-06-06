import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
from datetime import datetime
import uuid


class TemporalVectorStore:
    """
    Vector store with temporal awareness.
    Each document has version + timestamp metadata,
    enabling time-based retrieval and version comparison.
    """

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="chronolens_documents",
            metadata={"hnsw:space": "cosine"}
        )
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")

    def add_document_version(
        self,
        document_id: str,
        version: int,
        timestamp: str,
        chunks: List[Dict],
        doc_name: str,
        doc_type: str = "general"
    ) -> List[str]:
        """
        Add a versioned document to the store.

        Args:
            document_id: Logical document ID (same across versions)
            version: Version number (1, 2, 3, ...)
            timestamp: ISO format date (e.g., "2024-03-15")
            chunks: List of dicts with 'text', 'chunk_index'
            doc_name: Human-readable name
            doc_type: Category (contract, policy, regulation, etc.)

        Returns:
            List of chunk IDs added
        """
        if not chunks:
            return []

        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedder.encode(texts, show_progress_bar=False).tolist()

        ids = []
        metadatas = []

        for chunk in chunks:
            chunk_id = f"{document_id}_v{version}_c{chunk['chunk_index']}_{uuid.uuid4().hex[:6]}"
            ids.append(chunk_id)
            metadatas.append({
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
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

        return ids

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        document_id: Optional[str] = None,
        version: Optional[int] = None,
        timestamp_after: Optional[str] = None,
        timestamp_before: Optional[str] = None
    ) -> Dict:
        """Query with optional temporal filters."""
        query_embedding = self.embedder.encode([query_text]).tolist()

        # Build metadata filter — ChromaDB requires $and for multiple conditions
        conditions = []
        if document_id:
            conditions.append({"document_id": {"$eq": document_id}})
        if version is not None:
            conditions.append({"version": {"$eq": version}})

        if len(conditions) == 0:
            where_filter = None
        elif len(conditions) == 1:
            where_filter = conditions[0]
        else:
            where_filter = {"$and": conditions}

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where_filter
        )

        return results

    def get_all_versions(self, document_id: str) -> List[Dict]:
        """Get all versions of a document."""
        results = self.collection.get(
            where={"document_id": document_id}
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
    
    def get_version_chunks(self, document_id: str, version: int) -> List[Dict]:
        """
        Fetch ALL chunks for a specific version, including their embeddings.
        Used by the semantic diff engine for embedding-level alignment.
        """
        results = self.collection.get(
            where={"$and": [
                {"document_id": {"$eq": document_id}},
                {"version": {"$eq": version}},
            ]},
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
    def count(self) -> int:
        return self.collection.count()
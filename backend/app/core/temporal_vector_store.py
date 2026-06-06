import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict, Optional
from datetime import datetime
import uuid


class TemporalVectorStore:
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

    def add_document_version(
        self,
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
            query_texts=[query_text],
            n_results=n_results,
            where=where_filter
        )

        return results

    def get_all_versions(self, document_id: str) -> List[Dict]:
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
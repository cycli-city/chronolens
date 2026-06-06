import os
from typing import List, Dict, Optional
from supabase import create_client, Client
from chromadb.utils import embedding_functions
import numpy as np


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


class TemporalVectorStore:
    """
    Vector store backed by Supabase Postgres + pgvector.
    - Embeddings: 384-dim (all-MiniLM-L6-v2 via ONNX)
    - Persistence: Postgres — survives any restart
    - Multi-tenancy: user_id filter on every query + RLS as defense in depth
    """

    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"
            )
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        self.embedder = embedding_functions.DefaultEmbeddingFunction()

    def _embed(self, texts: List[str]) -> List[List[float]]:
        result = self.embedder(texts)
        if isinstance(result, np.ndarray):
            return result.tolist()
        return [list(v) for v in result]

    # ─────────────────────── WRITE ───────────────────────

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

        # Insert document row
        doc_resp = (
            self.client.table("documents")
            .insert({
                "user_id": user_id,
                "document_id": document_id,
                "version": version,
                "doc_name": doc_name,
                "doc_type": doc_type,
                "doc_date": timestamp,
            })
            .execute()
        )
        if not doc_resp.data:
            raise RuntimeError("Failed to insert document row")
        document_pk = doc_resp.data[0]["id"]

        # Embed all chunks
        texts = [c["text"] for c in chunks]
        embeddings = self._embed(texts)

        # Bulk insert chunks
        rows = [
            {
                "document_pk": document_pk,
                "user_id": user_id,
                "chunk_index": c["chunk_index"],
                "content": c["text"],
                "embedding": embeddings[i],
            }
            for i, c in enumerate(chunks)
        ]
        self.client.table("chunks").insert(rows).execute()
        return [str(c["chunk_index"]) for c in chunks]

    # ─────────────────────── READ ───────────────────────

    def query(
        self,
        user_id: str,
        query_text: str,
        n_results: int = 5,
        document_id: Optional[str] = None,
        version: Optional[int] = None,
    ) -> Dict:
        query_embedding = self._embed([query_text])[0]

        try:
            resp = self.client.rpc(
                "match_chunks_for_user",
                {
                    "p_user_id": user_id,
                    "p_query_embedding": query_embedding,
                    "p_match_count": n_results,
                    "p_document_id": document_id,
                    "p_version": version,
                },
            ).execute()
            rows = resp.data or []
        except Exception as e:
            print(f"Vector query failed: {e}")
            rows = []

        if not rows:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        return {
            "documents": [[r["content"] for r in rows]],
            "metadatas": [[{
                "document_id": r["document_id"],
                "version": r["version"],
                "doc_name": r["doc_name"],
                "timestamp": str(r["doc_date"]),
                "chunk_index": r["chunk_index"],
            } for r in rows]],
            "distances": [[1 - r["similarity"] for r in rows]],
        }

    def get_all_versions(self, user_id: str, document_id: str) -> List[Dict]:
        resp = (
            self.client.table("documents")
            .select("version,doc_date,doc_name")
            .eq("user_id", user_id)
            .eq("document_id", document_id)
            .order("version")
            .execute()
        )
        return [
            {
                "version": r["version"],
                "timestamp": str(r["doc_date"]),
                "doc_name": r["doc_name"],
            }
            for r in (resp.data or [])
        ]

    def list_user_documents(self, user_id: str) -> List[str]:
        resp = (
            self.client.table("documents")
            .select("document_id")
            .eq("user_id", user_id)
            .execute()
        )
        return sorted({r["document_id"] for r in (resp.data or [])})

    def get_version_chunks(
        self, user_id: str, document_id: str, version: int
    ) -> List[Dict]:
        # Find document pk
        doc_resp = (
            self.client.table("documents")
            .select("id")
            .eq("user_id", user_id)
            .eq("document_id", document_id)
            .eq("version", version)
            .limit(1)
            .execute()
        )
        if not doc_resp.data:
            return []
        document_pk = doc_resp.data[0]["id"]

        chunks_resp = (
            self.client.table("chunks")
            .select("chunk_index,content,embedding")
            .eq("user_id", user_id)
            .eq("document_pk", document_pk)
            .order("chunk_index")
            .execute()
        )

        out = []
        for r in (chunks_resp.data or []):
            emb = r.get("embedding")
            if isinstance(emb, str):
                emb = [
                    float(x)
                    for x in emb.strip("[]").split(",")
                    if x.strip()
                ]
            out.append({
                "text": r["content"],
                "chunk_index": r["chunk_index"],
                "embedding": emb,
            })
        return out

    def count(self, user_id: Optional[str] = None) -> int:
        q = self.client.table("chunks").select("id", count="exact")
        if user_id:
            q = q.eq("user_id", user_id)
        resp = q.execute()
        return resp.count or 0
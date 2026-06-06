import os
from typing import Optional
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.temporal_vector_store import TemporalVectorStore


class TemporalRAGEngine:
    def __init__(self):
        self.vector_store = TemporalVectorStore()
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=1500
        )

    def _format_chunks(self, results: dict) -> str:
        if not results or not results.get("documents"):
            return "No relevant content found."
        formatted = []
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        for i, (doc, meta) in enumerate(zip(docs, metas)):
            formatted.append(
                f"[SOURCE {i+1}] Version {meta.get('version')} | "
                f"Date: {meta.get('timestamp')} | Doc: {meta.get('doc_name')}\n{doc}\n"
            )
        return "\n---\n".join(formatted)

    def _extract_sources(self, results: dict) -> list:
        sources = []
        if results.get("metadatas"):
            seen = set()
            for meta in results["metadatas"][0]:
                key = f"{meta.get('version')}_{meta.get('timestamp')}"
                if key not in seen:
                    sources.append({
                        "version": meta.get("version"),
                        "timestamp": meta.get("timestamp"),
                        "doc_name": meta.get("doc_name")
                    })
                    seen.add(key)
        return sources

    def query(self, user_id: str, question: str, document_id: str) -> dict:
        question = question[:1000].strip()
        results = self.vector_store.query(
            user_id=user_id, query_text=question,
            n_results=4, document_id=document_id
        )
        context = self._format_chunks(results)

        system_prompt = """You are ChronoLens, a precise document intelligence assistant.
Answer questions strictly based on the provided document sources.
Always cite which source/version your answer comes from.
If the answer is not in the sources, say so clearly.
Never make up information."""
        user_prompt = f"Document sources:\n{context}\n\nQuestion: {question}\n\nAnswer with citations:"

        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        return {
            "answer": response.content,
            "sources": self._extract_sources(results),
            "document_id": document_id
        }

    def compare_versions(
        self, user_id: str, document_id: str,
        version_a: int, version_b: int, aspect: Optional[str] = None
    ) -> dict:
        focus = aspect if aspect else "everything"
        results_a = self.vector_store.query(
            user_id=user_id, query_text=aspect or "main content obligations terms",
            n_results=4, document_id=document_id, version=version_a
        )
        results_b = self.vector_store.query(
            user_id=user_id, query_text=aspect or "main content obligations terms",
            n_results=4, document_id=document_id, version=version_b
        )

        system_prompt = """You are ChronoLens, a temporal document analysis expert.
Identify what changed between two versions of a document.
Organize your response as:
1. ADDED — what is new
2. REMOVED — what was removed
3. MODIFIED — what changed
4. UNCHANGED — what stayed
5. RISK ASSESSMENT — changes carrying legal or business risk"""
        user_prompt = (
            f"Compare versions for changes related to: {focus}\n\n"
            f"VERSION {version_a}:\n{self._format_chunks(results_a)}\n\n"
            f"VERSION {version_b}:\n{self._format_chunks(results_b)}\n\n"
            f"Provide the comparison:"
        )

        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        return {
            "document_id": document_id,
            "version_a": version_a,
            "version_b": version_b,
            "aspect": aspect or "general",
            "analysis": response.content,
            "sources_a": self._extract_sources(results_a),
            "sources_b": self._extract_sources(results_b)
        }

    def timeline_summary(self, user_id: str, document_id: str) -> dict:
        versions = self.vector_store.get_all_versions(user_id, document_id)
        if not versions:
            return {"error": f"No versions found for {document_id}"}
        if len(versions) == 1:
            return {
                "document_id": document_id,
                "message": "Only one version exists. Upload more to see evolution.",
                "versions": versions
            }

        all_context = ""
        for v in versions:
            results = self.vector_store.query(
                user_id=user_id, query_text="summary overview purpose scope",
                n_results=2, document_id=document_id, version=v["version"]
            )
            all_context += f"\n\n=== VERSION {v['version']} ({v['timestamp']}) ===\n{self._format_chunks(results)}"

        system_prompt = """You are ChronoLens, a document timeline analyst.
Summarize how this document evolved over time, including the narrative arc,
why changes happened, and what the current version represents."""
        user_prompt = f"All versions of '{document_id}':\n{all_context}\n\nCreate a timeline summary:"

        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        return {
            "document_id": document_id,
            "total_versions": len(versions),
            "versions": versions,
            "timeline_narrative": response.content
        }
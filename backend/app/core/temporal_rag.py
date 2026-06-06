import os
from typing import Optional
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.temporal_vector_store import TemporalVectorStore


class TemporalRAGEngine:
    """
    The core engine that answers questions with temporal awareness.
    Retrieves chunks from specific versions and reasons over time.
    """

    def __init__(self):
        self.vector_store = TemporalVectorStore()
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=1500
        )

    def _format_chunks(self, results: dict) -> str:
        """Format retrieved chunks into context string."""
        if not results or not results.get("documents"):
            return "No relevant content found."

        formatted = []
        docs = results["documents"][0]
        metas = results["metadatas"][0]

        for i, (doc, meta) in enumerate(zip(docs, metas)):
            formatted.append(
                f"[SOURCE {i+1}] "
                f"Version {meta.get('version')} | "
                f"Date: {meta.get('timestamp')} | "
                f"Doc: {meta.get('doc_name')}\n"
                f"{doc}\n"
            )

        return "\n---\n".join(formatted)

    def query(
        self,
        question: str,
        document_id: str,
    ) -> dict:
        """
        Answer a general question about a document.
        """
        # Sanitize input
        question = question[:1000].strip()

        results = self.vector_store.query(
            query_text=question,
            n_results=4,
            document_id=document_id
        )

        context = self._format_chunks(results)

        system_prompt = """You are ChronoLens, a precise document intelligence assistant.
Answer questions strictly based on the provided document sources.
Always cite which source/version your answer comes from.
If the answer is not in the sources, say so clearly.
Never make up information."""

        user_prompt = f"""Document sources:
{context}

Question: {question}

Answer with citations to specific sources:"""

        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])

        sources = []
        if results.get("metadatas"):
            for meta in results["metadatas"][0]:
                sources.append({
                    "version": meta.get("version"),
                    "timestamp": meta.get("timestamp"),
                    "doc_name": meta.get("doc_name")
                })

        return {
            "answer": response.content,
            "sources": sources,
            "document_id": document_id
        }

    def compare_versions(
        self,
        document_id: str,
        version_a: int,
        version_b: int,
        aspect: Optional[str] = None
    ) -> dict:
        """
        THE TEMPORAL MAGIC — compare two versions of a document.
        Answers: what changed, what was added, what was removed.
        """
        focus = aspect if aspect else "everything"

        # Retrieve chunks from both versions
        results_a = self.vector_store.query(
            query_text=aspect or "main content obligations terms conditions",
            n_results=4,
            document_id=document_id,
            version=version_a
        )

        results_b = self.vector_store.query(
            query_text=aspect or "main content obligations terms conditions",
            n_results=4,
            document_id=document_id,
            version=version_b
        )

        context_a = self._format_chunks(results_a)
        context_b = self._format_chunks(results_b)

        system_prompt = """You are ChronoLens, a temporal document analysis expert.
Your job is to identify what changed between two versions of a document.
Be specific and structured. Always organize your response as:
1. ADDED — what is new in the later version
2. REMOVED — what was in the earlier version but is gone
3. MODIFIED — what exists in both but changed
4. UNCHANGED — key parts that stayed the same
5. RISK ASSESSMENT — any changes that could create legal or business risk

Base your analysis strictly on the provided content."""

        user_prompt = f"""Compare these two document versions for changes related to: {focus}

VERSION {version_a} CONTENT:
{context_a}

VERSION {version_b} CONTENT:
{context_b}

Provide a detailed temporal comparison:"""

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

    def timeline_summary(self, document_id: str) -> dict:
        """
        Summarize how a document evolved across ALL versions.
        """
        versions = self.vector_store.get_all_versions(document_id)

        if not versions:
            return {"error": f"No versions found for {document_id}"}

        if len(versions) == 1:
            return {
                "document_id": document_id,
                "message": "Only one version exists. Upload more versions to see evolution.",
                "versions": versions
            }

        # Build context from all versions
        all_context = ""
        for v in versions:
            results = self.vector_store.query(
                query_text="summary overview purpose scope",
                n_results=2,
                document_id=document_id,
                version=v["version"]
            )
            context = self._format_chunks(results)
            all_context += f"\n\n=== VERSION {v['version']} ({v['timestamp']}) ===\n{context}"

        system_prompt = """You are ChronoLens, a document timeline analyst.
Summarize how this document evolved over time.
Focus on the narrative arc: why did it change, what pressures caused changes,
what is the direction of change, and what does the current version represent
compared to the original."""

        user_prompt = f"""Here is the content from all versions of document '{document_id}':

{all_context}

Create a timeline summary showing how this document evolved:"""

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

    def _extract_sources(self, results: dict) -> list:
        """Extract source metadata from results."""
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
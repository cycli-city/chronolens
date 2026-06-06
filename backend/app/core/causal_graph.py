import os
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.temporal_vector_store import TemporalVectorStore
from app.core.semantic_diff import SemanticDiffEngine


class CausalGraphEngine:
    """
    Builds a causal timeline graph of a document's evolution.

    Nodes  = document versions
    Edges  = transitions between consecutive versions, each carrying:
               - diff summary (added/removed/modified counts)
               - change magnitude (the change_ratio)
               - inferred cause (LLM reasoning over what changed and why)

    The novelty: it doesn't just diff pairs in isolation — it reasons over
    the WHOLE chain to infer the narrative direction and likely drivers.
    """

    def __init__(self):
        self.vs = TemporalVectorStore()
        self.differ = SemanticDiffEngine()
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama-3.1-8b-instant",
            temperature=0.2,
            max_tokens=1800,
        )

    def build(self, document_id: str) -> dict:
        versions = self.vs.get_all_versions(document_id)

        if not versions:
            return {"error": f"No versions found for '{document_id}'."}
        if len(versions) == 1:
            return {
                "document_id": document_id,
                "nodes": [self._node(v) for v in versions],
                "edges": [],
                "message": "Only one version exists. Add more to build a causal graph."
            }

        nodes = [self._node(v) for v in versions]
        edges = []

        # Build an edge for each consecutive version pair
        for i in range(len(versions) - 1):
            va = versions[i]["version"]
            vb = versions[i + 1]["version"]

            diff = self.differ.diff(document_id, va, vb)
            summary = diff.get("summary", {})

            # Collect the actual changed text for cause inference
            change_snippets = []
            for c in diff.get("changes", []):
                if c["type"] == "modified":
                    change_snippets.append(
                        f"MODIFIED: {c.get('explanation', '')} "
                        f"(before: {c.get('before','')[:150]}...) "
                        f"(after: {c.get('after','')[:150]}...)"
                    )
                elif c["type"] == "added":
                    change_snippets.append(f"ADDED: {c.get('text','')[:150]}...")
                elif c["type"] == "removed":
                    change_snippets.append(f"REMOVED: {c.get('text','')[:150]}...")

            edges.append({
                "from_version": va,
                "to_version": vb,
                "from_date": versions[i]["timestamp"],
                "to_date": versions[i + 1]["timestamp"],
                "summary": summary,
                "change_magnitude": summary.get("change_ratio", 0),
                "change_snippets": change_snippets[:6],
                "inferred_cause": None,  # filled by LLM below
            })

        # Infer causes across the whole chain (single LLM pass for coherence)
        self._infer_causes(document_id, edges)

        return {
            "document_id": document_id,
            "nodes": nodes,
            "edges": edges,
            "total_transitions": len(edges),
        }

    def _node(self, v: dict) -> dict:
        return {
            "version": v["version"],
            "timestamp": v["timestamp"],
            "doc_name": v["doc_name"],
        }

    def _infer_causes(self, document_id: str, edges: list):
        """
        One LLM pass over the full chain so the inferred causes form a
        coherent narrative rather than disconnected guesses.
        """
        if not edges:
            return

        chain_desc = []
        for idx, e in enumerate(edges):
            snippets = "\n      ".join(e["change_snippets"]) or "no substantive textual changes"
            chain_desc.append(
                f"Transition {idx} (v{e['from_version']} on {e['from_date']} "
                f"-> v{e['to_version']} on {e['to_date']}):\n"
                f"   change magnitude: {round(e['change_magnitude']*100)}%\n"
                f"   changes:\n      {snippets}"
            )
        chain_text = "\n\n".join(chain_desc)

        system = (
            "You are a document forensics analyst. Given a chronological chain of "
            "changes to a single document, infer the LIKELY CAUSE or DRIVER behind "
            "each transition (e.g. regulatory pressure, risk mitigation, scope "
            "expansion, error correction, negotiation, policy update). "
            "Reason across the whole chain so causes form a coherent story. "
            'Respond ONLY with a JSON array: [{"transition":0,"cause":"...","confidence":"high|medium|low"}]. '
            "One concise sentence per cause. No markdown, no preamble."
        )
        user = f"Document: {document_id}\n\nChange chain:\n{chain_text}\n\nReturn the JSON array now:"

        try:
            resp = self.llm.invoke([
                SystemMessage(content=system),
                HumanMessage(content=user)
            ])
            text = resp.content.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            by_idx = {d["transition"]: d for d in data}
            for idx, e in enumerate(edges):
                info = by_idx.get(idx, {})
                e["inferred_cause"] = info.get("cause", "Cause could not be determined.")
                e["confidence"] = info.get("confidence", "low")
        except Exception:
            for e in edges:
                e["inferred_cause"] = "Cause inference unavailable."
                e["confidence"] = "low"
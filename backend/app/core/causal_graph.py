import os
import json
from datetime import date
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.temporal_vector_store import TemporalVectorStore
from app.core.semantic_diff import SemanticDiffEngine
from app.core.event_correlator import EventCorrelator


class CausalGraphEngine:
    """
    Builds a causal timeline graph of a document's evolution.

    Nodes  = document versions
    Edges  = transitions between consecutive versions, each carrying:
               - diff summary (added/removed/modified counts)
               - change magnitude (the change_ratio)
               - correlated regulatory events (real citations with dates)
               - inferred cause (LLM reasoning GROUNDED in real events)

    The key upgrade over v1: LLM no longer guesses blindly.
    It receives real regulatory events that occurred near each change
    and uses them as evidence for its causal explanation.
    """

    def __init__(self):
        self.vs = TemporalVectorStore()
        self.differ = SemanticDiffEngine()
        self.correlator = EventCorrelator()
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=2000,
        )

    def build(self, user_id: str, document_id: str) -> dict:
        versions = self.vs.get_all_versions(user_id, document_id)

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

        for i in range(len(versions) - 1):
            va = versions[i]
            vb = versions[i + 1]

            diff = self.differ.diff(user_id, document_id, va["version"], vb["version"])
            summary = diff.get("summary", {})

            # Collect changed chunks for correlation
            changed_chunks = [
                c for c in diff.get("changes", [])
                if c["type"] in ("modified", "removed", "added")
            ]

            # Correlate with real regulatory events
            correlated_events = self.correlator.correlate_transition(
                change_date=vb["timestamp"],
                changed_chunks=changed_chunks,
                top_k=3,
            )

            # Build change snippets for LLM
            change_snippets = []
            for c in changed_chunks[:4]:
                if c["type"] == "modified":
                    change_snippets.append(
                        f"MODIFIED ({c.get('explanation', 'semantic change')}): "
                        f"{c.get('before', '')[:120]}... → {c.get('after', '')[:120]}..."
                    )
                elif c["type"] == "added":
                    change_snippets.append(f"ADDED: {c.get('text', '')[:150]}...")
                elif c["type"] == "removed":
                    change_snippets.append(f"REMOVED: {c.get('text', '')[:150]}...")

            edge = {
                "from_version": va["version"],
                "to_version": vb["version"],
                "from_date": va["timestamp"],
                "to_date": vb["timestamp"],
                "summary": summary,
                "change_magnitude": summary.get("change_ratio", 0),
                "change_snippets": change_snippets[:4],
                "correlated_events": correlated_events,
                "inferred_cause": None,
                "confidence": "low",
                "evidence_based": len(correlated_events) > 0,
            }
            edges.append(edge)

        # Infer causes grounded in real events
        self._infer_causes_grounded(document_id, edges)

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

    def _infer_causes_grounded(self, document_id: str, edges: list):
        """
        LLM cause inference grounded in real regulatory events.
        For transitions with correlated events, the LLM must cite them.
        For transitions with no correlated events, it falls back to reasoning.
        """
        if not edges:
            return

        chain_desc = []
        for idx, e in enumerate(edges):
            snippets = "\n      ".join(e["change_snippets"]) or "no substantive textual changes"
            magnitude = round(e["change_magnitude"] * 100)

            # Format correlated events as evidence
            if e["correlated_events"]:
                evidence = "\n      ".join([
                    f"• {ev['title']} ({ev['event_date']}, "
                    f"{ev['days_before_change']} days before change, "
                    f"semantic similarity={ev['semantic_score']:.2f}): "
                    f"{ev['description'][:150]}"
                    for ev in e["correlated_events"]
                ])
                evidence_block = f"REGULATORY EVIDENCE:\n      {evidence}"
            else:
                evidence_block = "REGULATORY EVIDENCE: No correlated events found in database."

            chain_desc.append(
                f"Transition {idx} "
                f"(v{e['from_version']} {e['from_date']} → v{e['to_version']} {e['to_date']}):\n"
                f"   change magnitude: {magnitude}%\n"
                f"   changes:\n      {snippets}\n"
                f"   {evidence_block}"
            )
        chain_text = "\n\n".join(chain_desc)

        system = (
            "You are a document forensics analyst with access to real regulatory event data.\n"
            "For each transition:\n"
            "- If REGULATORY EVIDENCE is provided, you MUST cite it. Start with 'Following [event name] on [date]...'\n"
            "- If no evidence is found, reason from the changes themselves.\n"
            "- Be specific, concise, one sentence per transition.\n"
            "- Include confidence: 'high' if regulatory evidence matches, 'medium' if partial, 'low' if no evidence.\n\n"
            'Respond ONLY with JSON: [{"transition":0,"cause":"...","confidence":"high|medium|low"}]\n'
            "No markdown, no preamble."
        )
        user = (
            f"Document: {document_id}\n\n"
            f"Full transition chain with regulatory evidence:\n{chain_text}\n\n"
            "Return the JSON array now:"
        )

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
        except Exception as ex:
            print(f"Causal inference failed: {ex}")
            for e in edges:
                if e["correlated_events"]:
                    top = e["correlated_events"][0]
                    e["inferred_cause"] = (
                        f"Likely triggered by {top['title']} ({top['event_date']}, "
                        f"{top['days_before_change']} days prior)"
                    )
                    e["confidence"] = "medium"
                else:
                    e["inferred_cause"] = "Cause could not be determined."
                    e["confidence"] = "low"
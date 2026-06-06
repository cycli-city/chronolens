import os
import json
import numpy as np
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.temporal_vector_store import TemporalVectorStore


class SemanticDiffEngine:
    """
    Embedding-level semantic diff between two document versions.

    Algorithm:
      1. Pull every chunk (with its embedding) from version A and version B
      2. Compute the cosine-similarity matrix between all A and B chunks
      3. For each A chunk, find its best UNUSED match in B:
           - similarity >= UNCHANGED_T  -> unchanged
           - MODIFIED_T <= sim < UNCHANGED_T -> modified (meaning shifted)
           - sim < MODIFIED_T -> removed (no counterpart in B)
      4. Any B chunk with no good match back to A -> added
      5. Only the modified pairs go to the LLM, purely to explain WHAT changed
    """

    UNCHANGED_T = 0.93   # near-identical meaning
    MODIFIED_T = 0.55    # related but changed
    MAX_EXPLAIN = 8      # cap LLM explanations for cost/speed

    def __init__(self):
        self.vs = TemporalVectorStore()
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=1500,
        )

    @staticmethod
    def _cosine_matrix(A, B):
        A = np.asarray(A, dtype=float)
        B = np.asarray(B, dtype=float)
        if A.size == 0 or B.size == 0:
            return np.zeros((len(A), len(B)))
        An = A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-10)
        Bn = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-10)
        return An @ Bn.T

    def diff(self, document_id: str, version_a: int, version_b: int) -> dict:
        chunks_a = self.vs.get_version_chunks(document_id, version_a)
        chunks_b = self.vs.get_version_chunks(document_id, version_b)

        if not chunks_a and not chunks_b:
            return {"error": "No chunks found for either version."}

        emb_a = [c["embedding"] for c in chunks_a]
        emb_b = [c["embedding"] for c in chunks_b]
        S = self._cosine_matrix(emb_a, emb_b)  # shape (len_a, len_b)

        changes = []
        modified_pairs = []
        matched_b = set()
        counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}

        # Classify every A chunk (each B chunk can only be matched once)
        for i, ca in enumerate(chunks_a):
            if S.shape[1] == 0:
                counts["removed"] += 1
                changes.append({
                    "type": "removed", "a_index": ca["chunk_index"],
                    "text": ca["text"], "similarity": 0.0
                })
                continue

            # Mask out already-matched B chunks so they can't be reused
            row = S[i].copy()
            for used in matched_b:
                row[used] = -1.0

            j = int(np.argmax(row))
            score = float(row[j])

            if score >= self.UNCHANGED_T:
                counts["unchanged"] += 1
                matched_b.add(j)
            elif score >= self.MODIFIED_T:
                counts["modified"] += 1
                matched_b.add(j)
                pair = {
                    "type": "modified",
                    "a_index": ca["chunk_index"],
                    "b_index": chunks_b[j]["chunk_index"],
                    "similarity": round(score, 3),
                    "before": ca["text"],
                    "after": chunks_b[j]["text"],
                    "explanation": None,
                }
                changes.append(pair)
                modified_pairs.append(pair)
            else:
                counts["removed"] += 1
                # Use the original unmasked similarity for display (not the -1 mask)
                real_score = float(np.max(S[i])) if S.shape[1] > 0 else 0.0
                changes.append({
                    "type": "removed", "a_index": ca["chunk_index"],
                    "text": ca["text"], "similarity": round(real_score, 3)
                })

        # Any unmatched B chunk with no real counterpart in A = added
        for j, cb in enumerate(chunks_b):
            if j in matched_b:
                continue
            best = float(np.max(S[:, j])) if S.shape[0] > 0 else 0.0
            if best < self.MODIFIED_T:
                counts["added"] += 1
                changes.append({
                    "type": "added", "b_index": cb["chunk_index"],
                    "text": cb["text"], "similarity": round(best, 3)
                })

        total = max(sum(counts.values()), 1)
        change_ratio = round(
            (counts["added"] + counts["removed"] + counts["modified"]) / total, 3
        )

        # Explain only the most-changed modified pairs
        to_explain = sorted(modified_pairs, key=lambda p: p["similarity"])[: self.MAX_EXPLAIN]
        if to_explain:
            self._explain(to_explain)

        # Sort for readable output: modified, added, removed, then unchanged
        order = {"modified": 0, "added": 1, "removed": 2, "unchanged": 3}
        changes.sort(key=lambda c: (order.get(c["type"], 9),
                                    c.get("a_index", c.get("b_index", 0))))

        return {
            "document_id": document_id,
            "version_a": version_a,
            "version_b": version_b,
            "summary": {**counts, "change_ratio": change_ratio},
            "changes": changes,
        }

    def _explain(self, pairs):
        """Ask the LLM to explain each modified pair in one sentence (JSON out)."""
        items = []
        for idx, p in enumerate(pairs):
            items.append(
                f'{{"id": {idx}, '
                f'"before": {json.dumps(p["before"][:600])}, '
                f'"after": {json.dumps(p["after"][:600])}}}'
            )
        payload = "[" + ",".join(items) + "]"

        system = (
            "You are a precise document diff analyst. For each before/after pair, "
            "describe in ONE concise sentence what semantically changed. "
            'Respond ONLY with a JSON array like [{"id":0,"change":"..."}]. '
            "No markdown, no preamble, no extra text."
        )
        user = f"Pairs:\n{payload}\n\nReturn the JSON array now:"

        try:
            resp = self.llm.invoke([
                SystemMessage(content=system),
                HumanMessage(content=user)
            ])
            text = resp.content.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            by_id = {d["id"]: d.get("change", "") for d in data}
            for idx, p in enumerate(pairs):
                p["explanation"] = by_id.get(idx, "Change detected.")
        except Exception:
            for p in pairs:
                p["explanation"] = "Semantic change detected (explanation unavailable)."
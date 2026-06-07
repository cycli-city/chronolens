"""
Baseline diff methods for benchmarking ChronoLens against.

Each baseline classifies version-A chunks into:
  unchanged / modified / removed
and returns:
  - labels_a: list[str]   (per-A-chunk labels)
  - counts: dict          (aggregate counts)
  - runtime_ms: float
  - llm_calls: int        (for cost tracking)
"""
import time
import difflib
import os
import json
from typing import List, Dict
from app.core.temporal_vector_store import TemporalVectorStore
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage


class GitStyleDiffBaseline:
    """
    Line-by-line diff like 'git diff' — what every dev tool does today.
    Chunks classified by line-level overlap.
    """
    UNCHANGED_T = 0.95
    MODIFIED_T = 0.50

    def __init__(self):
        self.vs = TemporalVectorStore()

    def run(self, user_id: str, document_id: str, va: int, vb: int) -> Dict:
        t0 = time.time()
        chunks_a = self.vs.get_version_chunks(user_id, document_id, va)
        chunks_b = self.vs.get_version_chunks(user_id, document_id, vb)

        labels_a = []
        matched_b = set()

        for ca in chunks_a:
            lines_a = ca["text"].splitlines()
            best_j, best_score = -1, -1.0
            for j, cb in enumerate(chunks_b):
                if j in matched_b:
                    continue
                lines_b = cb["text"].splitlines()
                # Git-style: ratio of matching lines
                matcher = difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False)
                score = matcher.ratio()
                if score > best_score:
                    best_score = score
                    best_j = j

            if best_score >= self.UNCHANGED_T:
                labels_a.append("unchanged")
                matched_b.add(best_j)
            elif best_score >= self.MODIFIED_T:
                labels_a.append("modified")
                matched_b.add(best_j)
            else:
                labels_a.append("removed")

        counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
        for lbl in labels_a:
            counts[lbl] += 1
        # count adds
        for j in range(len(chunks_b)):
            if j not in matched_b:
                counts["added"] += 1

        return {
            "labels_a": labels_a,
            "counts": counts,
            "runtime_ms": round((time.time() - t0) * 1000, 1),
            "llm_calls": 0,
        }


class TextDiffBaseline:
    """
    Character-level difflib — what we used as ground truth before.
    Kept here so we can include it in comparison tables.
    """
    UNCHANGED_T = 0.95
    MODIFIED_T = 0.40

    def __init__(self):
        self.vs = TemporalVectorStore()

    def run(self, user_id: str, document_id: str, va: int, vb: int) -> Dict:
        t0 = time.time()
        chunks_a = self.vs.get_version_chunks(user_id, document_id, va)
        chunks_b = self.vs.get_version_chunks(user_id, document_id, vb)

        labels_a = []
        matched_b = set()
        for ca in chunks_a:
            best_j, best_score = -1, -1.0
            for j, cb in enumerate(chunks_b):
                if j in matched_b:
                    continue
                ratio = difflib.SequenceMatcher(
                    None, ca["text"], cb["text"], autojunk=False
                ).ratio()
                if ratio > best_score:
                    best_score = ratio
                    best_j = j

            if best_score >= self.UNCHANGED_T:
                labels_a.append("unchanged")
                matched_b.add(best_j)
            elif best_score >= self.MODIFIED_T:
                labels_a.append("modified")
                matched_b.add(best_j)
            else:
                labels_a.append("removed")

        counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
        for lbl in labels_a:
            counts[lbl] += 1
        for j in range(len(chunks_b)):
            if j not in matched_b:
                counts["added"] += 1

        return {
            "labels_a": labels_a,
            "counts": counts,
            "runtime_ms": round((time.time() - t0) * 1000, 1),
            "llm_calls": 0,
        }


class PureLLMBaseline:
    """
    Naive approach: feed both versions to LLM, ask it to classify each chunk.
    This is what someone would build with no embedding pipeline.
    """

    def __init__(self):
        self.vs = TemporalVectorStore()
        self.llm = ChatGroq(
            api_key=os.getenv("GROQ_API_KEY"),
            model_name="llama-3.1-8b-instant",
            temperature=0.0,
            max_tokens=2000,
        )

    def run(self, user_id: str, document_id: str, va: int, vb: int) -> Dict:
        t0 = time.time()
        chunks_a = self.vs.get_version_chunks(user_id, document_id, va)
        chunks_b = self.vs.get_version_chunks(user_id, document_id, vb)

        # Build a single prompt with all A and B chunks numbered
        a_text = "\n\n".join(
            f"A[{i}]: {c['text'][:400]}"
            for i, c in enumerate(chunks_a)
        )
        b_text = "\n\n".join(
            f"B[{i}]: {c['text'][:400]}"
            for i, c in enumerate(chunks_b)
        )

        system = (
            "You are a document diff classifier. For each chunk in document A, "
            "classify it as one of: 'unchanged', 'modified', or 'removed' "
            "relative to document B. Return ONLY a JSON array of strings in order, "
            'one per A chunk. Example: ["unchanged","modified","removed","unchanged"]. '
            "No preamble, no explanation."
        )
        user_msg = (
            f"DOCUMENT A ({len(chunks_a)} chunks):\n{a_text}\n\n"
            f"DOCUMENT B ({len(chunks_b)} chunks):\n{b_text}\n\n"
            f"Return the JSON array of {len(chunks_a)} classifications now:"
        )

        labels_a = ["unchanged"] * len(chunks_a)
        try:
            resp = self.llm.invoke([
                SystemMessage(content=system),
                HumanMessage(content=user_msg)
            ])
            text = resp.content.strip().replace("```json", "").replace("```", "").strip()
            # Find the JSON array in the response
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end + 1])
                for i, lbl in enumerate(parsed):
                    if i < len(labels_a) and lbl in ("unchanged", "modified", "removed"):
                        labels_a[i] = lbl
        except Exception as e:
            print(f"  LLM baseline failed: {e}")

        counts = {"added": 0, "removed": 0, "modified": 0, "unchanged": 0}
        for lbl in labels_a:
            counts[lbl] += 1
        # LLM can't reliably count added — leave as 0 (known limitation, that's the point)

        return {
            "labels_a": labels_a,
            "counts": counts,
            "runtime_ms": round((time.time() - t0) * 1000, 1),
            "llm_calls": 1,
        }
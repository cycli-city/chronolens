"""
Evaluates ChronoLens semantic diff against a textual-diff baseline.

Methodology:
  - Same chunking for both methods
  - Baseline: difflib SequenceMatcher ratio per chunk pair → classify
  - Predicted: ChronoLens semantic diff (cosine similarity of embeddings)
  - Compare per-A-chunk labels → confusion matrix → P/R/F1
"""
import difflib
from typing import Dict, List
from app.core.temporal_vector_store import TemporalVectorStore
from app.core.semantic_diff import SemanticDiffEngine


CLASSES = ["unchanged", "modified", "removed", "added"]


class Evaluator:
    # Same thresholds the semantic diff uses, but on text ratio
    UNCHANGED_T = 0.95
    MODIFIED_T = 0.40

    def __init__(self):
        self.vs = TemporalVectorStore()
        self.semantic = SemanticDiffEngine()

    # ─────────────────────── BASELINE ───────────────────────

    def text_baseline(
        self, user_id: str, document_id: str, va: int, vb: int
    ) -> Dict:
        chunks_a = self.vs.get_version_chunks(user_id, document_id, va)
        chunks_b = self.vs.get_version_chunks(user_id, document_id, vb)

        # Per-A label, mirrors semantic diff's greedy one-to-one match
        labels_a = []
        matched_b = set()

        for ca in chunks_a:
            best_j = -1
            best_score = -1.0
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

        # Added: unmatched B chunks with no strong match back to A
        added_count = 0
        for j, cb in enumerate(chunks_b):
            if j in matched_b:
                continue
            best_a = 0.0
            for ca in chunks_a:
                r = difflib.SequenceMatcher(
                    None, ca["text"], cb["text"], autojunk=False
                ).ratio()
                if r > best_a:
                    best_a = r
            if best_a < self.MODIFIED_T:
                added_count += 1

        counts = {"added": added_count, "removed": 0, "modified": 0, "unchanged": 0}
        for lbl in labels_a:
            counts[lbl] += 1

        return {
            "labels_a": labels_a,
            "counts": counts,
            "total_chunks_a": len(chunks_a),
            "total_chunks_b": len(chunks_b),
        }

    # ─────────────────────── PREDICTION ───────────────────────

    def chronolens_predict(
        self, user_id: str, document_id: str, va: int, vb: int, total_a: int
    ) -> Dict:
        result = self.semantic.diff(user_id, document_id, va, vb)
        summary = result.get("summary", {})

        # Reconstruct per-A labels: default unchanged, override from changes list
        labels_a = ["unchanged"] * total_a
        for c in result.get("changes", []):
            if c["type"] == "added":
                continue
            idx = c.get("a_index")
            if idx is not None and 0 <= idx < total_a:
                labels_a[idx] = c["type"]

        return {
            "labels_a": labels_a,
            "counts": {
                "added": summary.get("added", 0),
                "removed": summary.get("removed", 0),
                "modified": summary.get("modified", 0),
                "unchanged": summary.get("unchanged", 0),
            },
        }

    # ─────────────────────── METRICS ───────────────────────

    @staticmethod
    def confusion_matrix(labels_true: List[str], labels_pred: List[str]) -> Dict:
        matrix = {c: {c2: 0 for c2 in CLASSES} for c in CLASSES}
        for t, p in zip(labels_true, labels_pred):
            if t in matrix and p in matrix[t]:
                matrix[t][p] += 1
        return matrix

    @staticmethod
    def per_class_metrics(matrix: Dict) -> Dict:
        out = {}
        for cls in CLASSES:
            tp = matrix[cls][cls]
            fp = sum(matrix[o][cls] for o in CLASSES if o != cls)
            fn = sum(matrix[cls][o] for o in CLASSES if o != cls)
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
            out[cls] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "support": tp + fn,
            }
        return out

    @staticmethod
    def macro_average(per_class: Dict) -> Dict:
        # Macro avg over classes that have support > 0
        active = [m for m in per_class.values() if m["support"] > 0]
        if not active:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        return {
            "precision": round(sum(m["precision"] for m in active) / len(active), 4),
            "recall": round(sum(m["recall"] for m in active) / len(active), 4),
            "f1": round(sum(m["f1"] for m in active) / len(active), 4),
        }

    @staticmethod
    def agreement(labels_true: List[str], labels_pred: List[str]) -> float:
        if not labels_true:
            return 0.0
        matches = sum(1 for a, b in zip(labels_true, labels_pred) if a == b)
        return round(matches / len(labels_true), 4)

    # ─────────────────────── PER-PAIR ───────────────────────

    def evaluate_pair(
        self, user_id: str, document_id: str, va: int, vb: int
    ) -> Dict:
        baseline = self.text_baseline(user_id, document_id, va, vb)
        predicted = self.chronolens_predict(
            user_id, document_id, va, vb, baseline["total_chunks_a"]
        )

        labels_true = baseline["labels_a"]
        labels_pred = predicted["labels_a"]

        cm = self.confusion_matrix(labels_true, labels_pred)
        per_class = self.per_class_metrics(cm)
        macro = self.macro_average(per_class)
        agr = self.agreement(labels_true, labels_pred)

        return {
            "document_id": document_id,
            "version_a": va,
            "version_b": vb,
            "total_chunks_a": baseline["total_chunks_a"],
            "total_chunks_b": baseline["total_chunks_b"],
            "baseline_counts": baseline["counts"],
            "predicted_counts": predicted["counts"],
            "per_chunk_baseline": labels_true,
            "per_chunk_predicted": labels_pred,
            "confusion_matrix": cm,
            "per_class": per_class,
            "macro": macro,
            "agreement": agr,
        }
"""
Correlates document changes with real regulatory events.

For each version transition (date_a → date_b), finds regulatory events
that occurred within a time window and ranks them by:
  1. Temporal proximity to the change
  2. Semantic similarity to the changed content
"""
import os
from datetime import date, timedelta
from typing import List, Dict, Optional
from supabase import create_client
from chromadb.utils import embedding_functions
import numpy as np


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
LOOKBACK_DAYS = 180   # look 6 months before the change
LOOKAHEAD_DAYS = 30   # and 1 month after


class EventCorrelator:
    """
    Finds real-world regulatory events that may have caused
    a document change, ranked by temporal + semantic relevance.
    """

    def __init__(self):
        self.client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        self.embedder = embedding_functions.DefaultEmbeddingFunction()

    def _embed(self, texts: List[str]) -> List[List[float]]:
        result = self.embedder(texts)
        if isinstance(result, np.ndarray):
            return [[float(x) for x in row] for row in result]
        return [[float(x) for x in row] for row in result]

    def _cosine(self, a: List[float], b: List[float]) -> float:
        va = np.array(a)
        vb = np.array(b)
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        if denom == 0:
            return 0.0
        return float(np.dot(va, vb) / denom)

    def _days_between(self, event_date: str, change_date: str) -> int:
        """Days from event to change. Negative = event after change."""
        try:
            ed = date.fromisoformat(str(event_date))
            cd = date.fromisoformat(str(change_date))
            return (cd - ed).days
        except Exception:
            return 999

    def seed_events(self, events: List[Dict]):
        """Embed and insert regulatory events into Supabase."""
        descriptions = [e["description"] for e in events]
        embeddings = self._embed(descriptions)

        rows = []
        for i, ev in enumerate(events):
            rows.append({
                "event_date": ev["event_date"],
                "title": ev["title"],
                "description": ev["description"],
                "source_url": ev.get("source_url", ""),
                "jurisdiction": ev.get("jurisdiction", "EU"),
                "category": ev.get("category", "regulation"),
                "embedding": embeddings[i],
            })

        # Upsert by title to avoid duplicates
        for row in rows:
            existing = (
                self.client.table("regulatory_events")
                .select("id")
                .eq("title", row["title"])
                .execute()
            )
            if not existing.data:
                self.client.table("regulatory_events").insert(row).execute()

        return len(rows)

    def correlate(
        self,
        change_date: str,
        changed_text: str,
        jurisdiction: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict]:
        """
        Find regulatory events correlated with a document change.

        Args:
            change_date: Date of the document version that changed (YYYY-MM-DD)
            changed_text: The actual text that changed (from semantic diff)
            jurisdiction: Optional filter (EU, US, UK...)
            top_k: Number of top correlated events to return

        Returns:
            List of correlated events ranked by combined score
        """
        # Calculate date window
        try:
            cd = date.fromisoformat(change_date)
            window_start = (cd - timedelta(days=LOOKBACK_DAYS)).isoformat()
            window_end = (cd + timedelta(days=LOOKAHEAD_DAYS)).isoformat()
        except Exception:
            return []

        # Fetch candidate events within time window
        q = (
            self.client.table("regulatory_events")
            .select("*")
            .gte("event_date", window_start)
            .lte("event_date", window_end)
        )
        if jurisdiction:
            q = q.eq("jurisdiction", jurisdiction)

        resp = q.execute()
        candidates = resp.data or []

        if not candidates:
            return []

        # Embed the changed text
        change_embedding = self._embed([changed_text[:1000]])[0]

        # Score each candidate
        scored = []
        for ev in candidates:
            # Temporal score: closer = higher (exponential decay)
            days = self._days_between(ev["event_date"], change_date)
            if days < 0:
                # Event after change — weaker signal, penalize
                temporal_score = max(0.0, 1.0 - abs(days) / LOOKAHEAD_DAYS) * 0.5
            else:
                # Event before change — primary signal
                temporal_score = max(0.0, 1.0 - days / LOOKBACK_DAYS)

            # Semantic score: how related is the event to the changed text
            ev_embedding = ev.get("embedding")
            if ev_embedding:
                if isinstance(ev_embedding, str):
                    ev_embedding = [
                        float(x) for x in ev_embedding.strip("[]").split(",")
                        if x.strip()
                    ]
                semantic_score = self._cosine(change_embedding, ev_embedding)
            else:
                semantic_score = 0.0

            # Combined score: 60% temporal, 40% semantic
            combined = 0.6 * temporal_score + 0.4 * semantic_score

            scored.append({
                "title": ev["title"],
                "description": ev["description"],
                "event_date": str(ev["event_date"]),
                "source_url": ev.get("source_url", ""),
                "jurisdiction": ev["jurisdiction"],
                "category": ev["category"],
                "days_before_change": days,
                "temporal_score": round(temporal_score, 3),
                "semantic_score": round(semantic_score, 3),
                "combined_score": round(combined, 3),
            })

        # Sort by combined score, return top_k
        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        return scored[:top_k]

    def correlate_transition(
        self,
        change_date: str,
        changed_chunks: List[Dict],
        jurisdiction: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict]:
        """
        Correlate a full version transition (multiple changed chunks)
        by aggregating the most-changed text.
        """
        if not changed_chunks:
            return []

        # Concatenate the most semantically significant changed text
        combined_text = " ".join(
            c.get("before", c.get("text", ""))[:300]
            for c in changed_chunks[:5]
        )
        return self.correlate(change_date, combined_text, jurisdiction, top_k)
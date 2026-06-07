"""
Run a full evaluation:
  1. Ingest Wikipedia revisions for N articles
  2. Evaluate each consecutive version pair
  3. Aggregate metrics
  4. Persist to Supabase benchmark_runs / benchmark_pairs
"""
import os
import sys
import secrets
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

from app.core.wikipedia_loader import WikipediaLoader
from app.core.temporal_vector_store import TemporalVectorStore
from app.core.evaluator import Evaluator, CLASSES
from app.pipelines.chunker import TextChunker


# Wikipedia articles with rich edit histories
ARTICLES = [
    "General Data Protection Regulation",
    "Bitcoin",
    "Artificial intelligence",
    "Climate change",
    "European Union law",
]
VERSIONS_PER_ARTICLE = 4  # → 3 consecutive pairs per article


def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
        sys.exit(1)
    return create_client(url, key)


def get_or_create_benchmark_user(client) -> str:
    email = "benchmark@chronolens.dev"
    try:
        page = client.auth.admin.list_users()
        users = page if isinstance(page, list) else page.users if hasattr(page, "users") else []
        for u in users:
            if getattr(u, "email", None) == email:
                return u.id
    except Exception as e:
        print(f"Could not list users: {e}")

    print("Creating benchmark user...")
    new_pwd = "Bench-" + secrets.token_urlsafe(16)
    created = client.auth.admin.create_user({
        "email": email,
        "password": new_pwd,
        "email_confirm": True,
    })
    user_id = created.user.id if hasattr(created, "user") else created["user"]["id"]
    print(f"Benchmark user ID: {user_id}")
    return user_id


def wipe_user_data(client, user_id: str):
    """Clear previous benchmark data for clean runs."""
    print(f"Wiping previous benchmark data for {user_id[:8]}...")
    client.table("chunks").delete().eq("user_id", user_id).execute()
    client.table("documents").delete().eq("user_id", user_id).execute()


def slugify(title: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in title.lower())[:80]


def ingest_articles(user_id: str, client) -> list:
    """Ingest all articles. Return list of (document_id, version_count) tuples."""
    loader = WikipediaLoader()
    vs = TemporalVectorStore()
    chunker = TextChunker(chunk_size=800, overlap=150)

    ingested = []
    for title in ARTICLES:
        print(f"\nFetching '{title}'...")
        revs = loader.fetch_revisions_for_article(title, n_versions=VERSIONS_PER_ARTICLE)
        if len(revs) < 2:
            print(f"  Skipping — only {len(revs)} usable revisions")
            continue

        doc_id = slugify(title)
        for rev in revs:
            chunks = chunker.chunk(rev["content"])
            chunk_dicts = [
                {"text": c.text, "chunk_index": c.chunk_index}
                for c in chunks
            ]
            vs.add_document_version(
                user_id=user_id,
                document_id=doc_id,
                version=rev["version"],
                timestamp=rev["timestamp"],
                chunks=chunk_dicts,
                doc_name=title,
                doc_type="article",
            )
            print(f"  v{rev['version']} ({rev['timestamp']}): {len(chunks)} chunks")
        ingested.append((doc_id, len(revs)))
    return ingested


def aggregate_per_class(per_pair_results: list) -> dict:
    """Aggregate per-class metrics across all pairs by summing confusion matrices."""
    total_cm = {c: {c2: 0 for c2 in CLASSES} for c in CLASSES}
    for p in per_pair_results:
        for t in CLASSES:
            for q in CLASSES:
                total_cm[t][q] += p["confusion_matrix"][t][q]

    per_class = Evaluator.per_class_metrics(total_cm)
    macro = Evaluator.macro_average(per_class)
    return {"per_class": per_class, "macro": macro, "confusion_matrix": total_cm}


def run():
    client = get_supabase()
    user_id = get_or_create_benchmark_user(client)
    wipe_user_data(client, user_id)

    ingested = ingest_articles(user_id, client)
    if not ingested:
        print("\nNo articles ingested. Aborting.")
        return

    print("\n" + "=" * 60)
    print("Running evaluation across all consecutive version pairs...")
    print("=" * 60)

    evaluator = Evaluator()
    per_pair = []
    total_chunks = 0
    total_agreement = 0

    for doc_id, n_versions in ingested:
        for va in range(1, n_versions):
            vb = va + 1
            print(f"\n{doc_id}: v{va} -> v{vb}")
            try:
                result = evaluator.evaluate_pair(user_id, doc_id, va, vb)
            except Exception as e:
                print(f"  ERROR: {e}")
                continue

            per_pair.append(result)
            total_chunks += result["total_chunks_a"]
            total_agreement += int(result["agreement"] * result["total_chunks_a"])

            print(f"  baseline:  {result['baseline_counts']}")
            print(f"  predicted: {result['predicted_counts']}")
            print(f"  agreement: {result['agreement']*100:.1f}%  "
                  f"macro-F1: {result['macro']['f1']:.3f}")

    if not per_pair:
        print("\nNo pairs evaluated.")
        return

    overall_agreement = total_agreement / total_chunks if total_chunks else 0
    agg = aggregate_per_class(per_pair)

    print("\n" + "=" * 60)
    print("OVERALL RESULTS")
    print("=" * 60)
    print(f"Articles ingested:  {len(ingested)}")
    print(f"Pairs evaluated:    {len(per_pair)}")
    print(f"Total A chunks:     {total_chunks}")
    print(f"Agreement rate:     {overall_agreement*100:.2f}%")
    print(f"Macro Precision:    {agg['macro']['precision']:.3f}")
    print(f"Macro Recall:       {agg['macro']['recall']:.3f}")
    print(f"Macro F1:           {agg['macro']['f1']:.3f}")
    print("\nPer-class:")
    for cls, m in agg["per_class"].items():
        print(f"  {cls:11s}  P={m['precision']:.3f}  R={m['recall']:.3f}  "
              f"F1={m['f1']:.3f}  (n={m['support']})")

    # Persist run
    run_row = client.table("benchmark_runs").insert({
        "name": f"wikipedia_eval_{datetime.utcnow().isoformat()[:19]}",
        "dataset_source": "Wikipedia revisions API",
        "documents_count": len(ingested),
        "pairs_count": len(per_pair),
        "agreement_rate": overall_agreement,
        "macro_precision": agg["macro"]["precision"],
        "macro_recall": agg["macro"]["recall"],
        "macro_f1": agg["macro"]["f1"],
        "per_class_metrics": agg["per_class"],
        "notes": f"Articles: {[a for a, _ in ingested]}",
    }).execute()
    run_id = run_row.data[0]["id"]

    for p in per_pair:
        client.table("benchmark_pairs").insert({
            "run_id": run_id,
            "document_id": p["document_id"],
            "version_a": p["version_a"],
            "version_b": p["version_b"],
            "total_chunks_a": p["total_chunks_a"],
            "total_chunks_b": p["total_chunks_b"],
            "baseline_counts": p["baseline_counts"],
            "predicted_counts": p["predicted_counts"],
            "per_chunk_baseline": p["per_chunk_baseline"],
            "per_chunk_predicted": p["per_chunk_predicted"],
            "agreement_chunks": int(p["agreement"] * p["total_chunks_a"]),
            "total_compared": p["total_chunks_a"],
        }).execute()

    print(f"\nResults saved to benchmark_runs/{run_id}")
    print("Run again with: python -m scripts.run_evaluation")


if __name__ == "__main__":
    run()
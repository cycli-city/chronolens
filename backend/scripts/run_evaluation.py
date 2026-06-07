"""
Run a full comparison evaluation:
  1. Ingest Wikipedia revisions (or reuse if present)
  2. For each consecutive pair, run ALL methods:
       - git_diff (line-level)
       - text_diff (char-level, the original baseline = also acts as reference)
       - pure_llm (naive LLM approach)
       - chronolens (embedding-aligned semantic diff)
  3. Compute metrics for each method vs the text_diff reference
  4. Persist a benchmark_run + per-method aggregates + per-pair detail
"""
import os
import sys
import secrets
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

from app.core.wikipedia_loader import WikipediaLoader
from app.core.temporal_vector_store import TemporalVectorStore
from app.core.evaluator import Evaluator, CLASSES
from app.core.baselines import GitStyleDiffBaseline, TextDiffBaseline, PureLLMBaseline
from app.core.semantic_diff import SemanticDiffEngine
from app.pipelines.chunker import TextChunker


ARTICLES = [
    "General Data Protection Regulation",
    "Bitcoin",
    "Artificial intelligence",
    "Climate change",
    "European Union law",
]
VERSIONS_PER_ARTICLE = 4
REFERENCE_METHOD = "text_diff"  # used as ground truth proxy
COMPARED_METHODS = ["git_diff", "pure_llm", "chronolens"]


def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        sys.exit(1)
    return create_client(url, key)


def get_or_create_benchmark_user(client) -> str:
    email = "benchmark@chronolens.dev"
    try:
        page = client.auth.admin.list_users()
        users = page if isinstance(page, list) else (page.users if hasattr(page, "users") else [])
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
    return created.user.id if hasattr(created, "user") else created["user"]["id"]


def wipe_user_data(client, user_id: str):
    print(f"Wiping previous benchmark data for {user_id[:8]}...")
    client.table("chunks").delete().eq("user_id", user_id).execute()
    client.table("documents").delete().eq("user_id", user_id).execute()


def slugify(title: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in title.lower())[:80]


def ingest_articles(user_id: str) -> list:
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
            chunk_dicts = [{"text": c.text, "chunk_index": c.chunk_index} for c in chunks]
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


def chronolens_run(user_id, document_id, va, vb, total_a) -> dict:
    """Wrap the existing SemanticDiffEngine in the baseline result format."""
    import time
    semantic = SemanticDiffEngine()
    t0 = time.time()
    result = semantic.diff(user_id, document_id, va, vb)
    runtime = round((time.time() - t0) * 1000, 1)

    labels_a = ["unchanged"] * total_a
    for c in result.get("changes", []):
        if c["type"] == "added":
            continue
        idx = c.get("a_index")
        if idx is not None and 0 <= idx < total_a:
            labels_a[idx] = c["type"]

    summary = result.get("summary", {})
    return {
        "labels_a": labels_a,
        "counts": {
            "added": summary.get("added", 0),
            "removed": summary.get("removed", 0),
            "modified": summary.get("modified", 0),
            "unchanged": summary.get("unchanged", 0),
        },
        "runtime_ms": runtime,
        "llm_calls": 1 if summary.get("modified", 0) > 0 else 0,
    }


def aggregate_method(per_pair_for_method: list) -> dict:
    total_cm = {c: {c2: 0 for c2 in CLASSES} for c in CLASSES}
    total_correct = 0
    total_compared = 0
    total_runtime = 0.0
    total_llm = 0

    for p in per_pair_for_method:
        cm = p["confusion_matrix"]
        for t in CLASSES:
            for q in CLASSES:
                total_cm[t][q] += cm[t][q]
        total_correct += p["agreement_count"]
        total_compared += p["total_compared"]
        total_runtime += p["runtime_ms"]
        total_llm += p["llm_calls"]

    per_class = Evaluator.per_class_metrics(total_cm)
    macro = Evaluator.macro_average(per_class)
    return {
        "agreement_rate": round(total_correct / total_compared, 4) if total_compared else 0.0,
        "macro_precision": macro["precision"],
        "macro_recall": macro["recall"],
        "macro_f1": macro["f1"],
        "per_class": per_class,
        "total_runtime_ms": round(total_runtime, 1),
        "total_llm_calls": total_llm,
    }


def run():
    client = get_supabase()
    user_id = get_or_create_benchmark_user(client)
    wipe_user_data(client, user_id)

    ingested = ingest_articles(user_id)
    if not ingested:
        print("\nNo articles ingested. Aborting.")
        return

    print("\n" + "=" * 70)
    print("Running multi-method comparison...")
    print("=" * 70)

    git_diff = GitStyleDiffBaseline()
    text_diff = TextDiffBaseline()
    pure_llm = PureLLMBaseline()

    # Per-method, per-pair results
    pair_results = {m: [] for m in ["text_diff"] + COMPARED_METHODS}

    for doc_id, n_versions in ingested:
        for va in range(1, n_versions):
            vb = va + 1
            print(f"\n{doc_id}: v{va} -> v{vb}")

            # Reference: text_diff
            ref = text_diff.run(user_id, doc_id, va, vb)
            ref_labels = ref["labels_a"]
            total_a = len(ref_labels)
            print(f"  text_diff (reference):  {ref['counts']}  [{ref['runtime_ms']}ms]")

            method_outputs = {
                "text_diff": ref,
                "git_diff": git_diff.run(user_id, doc_id, va, vb),
                "pure_llm": pure_llm.run(user_id, doc_id, va, vb),
                "chronolens": chronolens_run(user_id, doc_id, va, vb, total_a),
            }

            for method, out in method_outputs.items():
                if method == "text_diff":
                    # Compare against itself = 100% (sanity check, still record)
                    cm = Evaluator.confusion_matrix(ref_labels, ref_labels)
                    agreement = 1.0
                else:
                    cm = Evaluator.confusion_matrix(ref_labels, out["labels_a"])
                    matches = sum(1 for a, b in zip(ref_labels, out["labels_a"]) if a == b)
                    agreement = matches / total_a if total_a else 0.0
                    print(f"  {method:12s} {out['counts']}  "
                          f"agreement={agreement*100:.1f}%  [{out['runtime_ms']}ms]")

                pair_results[method].append({
                    "document_id": doc_id,
                    "version_a": va,
                    "version_b": vb,
                    "labels": out["labels_a"],
                    "counts": out["counts"],
                    "runtime_ms": out["runtime_ms"],
                    "llm_calls": out["llm_calls"],
                    "confusion_matrix": cm,
                    "agreement_count": int(agreement * total_a),
                    "total_compared": total_a,
                })

    # Aggregate per method
    aggregates = {m: aggregate_method(pair_results[m]) for m in pair_results}

    print("\n" + "=" * 70)
    print("FINAL COMPARISON")
    print("=" * 70)
    print(f"{'Method':14s} {'Agreement':>10s} {'Precision':>10s} {'Recall':>10s} {'F1':>8s} {'Runtime':>12s} {'LLM Calls':>11s}")
    print("-" * 80)
    for method in ["text_diff", "git_diff", "pure_llm", "chronolens"]:
        a = aggregates[method]
        runtime_s = f"{a['total_runtime_ms']/1000:.1f}s"
        print(
            f"{method:14s} {a['agreement_rate']*100:>9.2f}% "
            f"{a['macro_precision']:>10.3f} {a['macro_recall']:>10.3f} "
            f"{a['macro_f1']:>8.3f} {runtime_s:>12s} {a['total_llm_calls']:>11d}"
        )

    # Persist
    pairs_count = len(pair_results["chronolens"])
    run_row = client.table("benchmark_runs").insert({
        "name": f"comparison_{datetime.utcnow().isoformat()[:19]}",
        "dataset_source": "Wikipedia revisions API",
        "documents_count": len(ingested),
        "pairs_count": pairs_count,
        "agreement_rate": aggregates["chronolens"]["agreement_rate"],
        "macro_precision": aggregates["chronolens"]["macro_precision"],
        "macro_recall": aggregates["chronolens"]["macro_recall"],
        "macro_f1": aggregates["chronolens"]["macro_f1"],
        "per_class_metrics": aggregates["chronolens"]["per_class"],
        "notes": f"Comparison of git_diff vs text_diff vs pure_llm vs chronolens",
    }).execute()
    run_id = run_row.data[0]["id"]

    # Persist method aggregates
    for method, a in aggregates.items():
        client.table("benchmark_methods").insert({
            "run_id": run_id,
            "method": method,
            "agreement_rate": a["agreement_rate"],
            "macro_precision": a["macro_precision"],
            "macro_recall": a["macro_recall"],
            "macro_f1": a["macro_f1"],
            "per_class": a["per_class"],
            "total_runtime_ms": a["total_runtime_ms"],
            "total_llm_calls": a["total_llm_calls"],
        }).execute()

    # Persist per-pair detail for ChronoLens only (avoid 4x bloat)
    for p in pair_results["chronolens"]:
        client.table("benchmark_pairs").insert({
            "run_id": run_id,
            "document_id": p["document_id"],
            "version_a": p["version_a"],
            "version_b": p["version_b"],
            "total_chunks_a": p["total_compared"],
            "total_chunks_b": p["total_compared"],
            "baseline_counts": pair_results["text_diff"][pair_results["chronolens"].index(p)]["counts"],
            "predicted_counts": p["counts"],
            "per_chunk_baseline": pair_results["text_diff"][pair_results["chronolens"].index(p)]["labels"],
            "per_chunk_predicted": p["labels"],
            "agreement_chunks": p["agreement_count"],
            "total_compared": p["total_compared"],
            "method": "chronolens",
            "runtime_ms": p["runtime_ms"],
            "llm_calls": p["llm_calls"],
        }).execute()

    print(f"\nRun saved: benchmark_runs/{run_id}")


if __name__ == "__main__":
    run()
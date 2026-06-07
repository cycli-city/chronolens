"""
Scale testing harness for ChronoLens.

Tests ingestion speed, query latency, and semantic diff performance
at increasing document scales. Results stored in Supabase.

Run with:
  python -m scripts.run_scale_test
"""
import os
import sys
import time
import secrets
import statistics
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client
from app.core.temporal_vector_store import TemporalVectorStore
from app.core.semantic_diff import SemanticDiffEngine
from app.pipelines.chunker import TextChunker


# Scale levels: (n_documents, chunks_per_doc)
# Total chunks = n_documents * chunks_per_doc
SCALE_LEVELS = [
    (5,   10),   # 50 chunks   — baseline
    (10,  10),   # 100 chunks
    (25,  10),   # 250 chunks
    (50,  10),   # 500 chunks
    (100, 10),   # 1000 chunks
]

QUERIES_PER_LEVEL = 20   # number of query latency measurements
CHUNK_SIZE = 800

# Synthetic document templates to vary content meaningfully
DOC_TEMPLATES = [
    "This agreement governs the terms and conditions of service between {party_a} and {party_b}. "
    "The parties agree to the following obligations: data processing, privacy compliance under GDPR Article {n}, "
    "payment terms of {n} days, and intellectual property rights. "
    "Either party may terminate this agreement with {n} days written notice. "
    "Disputes shall be resolved by arbitration in {city}.",

    "Section {n}: Data Protection and Privacy. The controller shall implement appropriate technical and "
    "organizational measures to ensure a level of security appropriate to the risk. "
    "Personal data shall be processed lawfully, fairly and transparently. "
    "Data subjects have the right to access, rectify, and erase their personal data. "
    "Breach notification shall occur within 72 hours of becoming aware of a breach.",

    "POLICY UPDATE {n}: Effective {date}, all employees must comply with the updated information security policy. "
    "Access controls shall be reviewed quarterly. Multi-factor authentication is mandatory for all systems. "
    "Incident response procedures must be followed within 4 hours of detection. "
    "Third-party vendors must demonstrate SOC2 Type II compliance before onboarding.",

    "Clause {n}: Intellectual Property Rights. All work product created by the service provider "
    "during the term of this agreement shall be considered work-for-hire. "
    "The client retains all rights, title, and interest in such work product. "
    "The service provider may not use client materials for any other purpose. "
    "Confidentiality obligations survive termination for a period of {n} years.",

    "Article {n}: Compliance Requirements. The organization must maintain compliance with "
    "ISO 27001, SOC 2 Type II, and applicable data protection regulations. "
    "Annual audits shall be conducted by an independent third party. "
    "Non-compliance may result in contract termination and financial penalties. "
    "All compliance documentation must be retained for {n} years.",
]


def generate_document_text(doc_index: int, version: int, chunk_count: int) -> str:
    """Generate synthetic document text of approximately chunk_count * CHUNK_SIZE chars."""
    template = DOC_TEMPLATES[doc_index % len(DOC_TEMPLATES)]
    paragraphs = []
    for i in range(chunk_count):
        para = template.format(
            party_a=f"Company_{doc_index}_{i}",
            party_b=f"Vendor_{doc_index}_{i}",
            n=doc_index * 10 + i + version,
            city=["London", "Paris", "Amsterdam", "Berlin", "Dublin"][i % 5],
            date=f"2024-0{(i % 9) + 1}-01",
        )
        # Add version-specific variation
        if version > 1 and i % 4 == 0:
            para += f" [Updated in version {version}: revised terms effective immediately.]"
        paragraphs.append(para)
    return "\n\n".join(paragraphs)


def get_or_create_scale_user(client) -> str:
    email = "scale-test@chronolens.dev"
    try:
        page = client.auth.admin.list_users()
        users = page if isinstance(page, list) else (page.users if hasattr(page, "users") else [])
        for u in users:
            if getattr(u, "email", None) == email:
                return u.id
    except Exception:
        pass
    created = client.auth.admin.create_user({
        "email": email,
        "password": "Scale-" + secrets.token_urlsafe(16),
        "email_confirm": True,
    })
    return created.user.id if hasattr(created, "user") else created["user"]["id"]


def wipe_scale_data(client, user_id: str):
    client.table("chunks").delete().eq("user_id", user_id).execute()
    client.table("documents").delete().eq("user_id", user_id).execute()


def measure_ingestion(
    vs: TemporalVectorStore,
    chunker: TextChunker,
    user_id: str,
    n_docs: int,
    chunks_per_doc: int
) -> dict:
    """Ingest n_docs documents and measure total time."""
    t0 = time.time()
    total_chunks = 0

    for doc_i in range(n_docs):
        doc_id = f"scale_doc_{doc_i:04d}"
        text = generate_document_text(doc_i, version=1, chunk_count=chunks_per_doc)
        chunks = chunker.chunk(text)
        chunk_dicts = [{"text": c.text, "chunk_index": c.chunk_index} for c in chunks]
        vs.add_document_version(
            user_id=user_id,
            document_id=doc_id,
            version=1,
            timestamp="2024-01-01",
            chunks=chunk_dicts,
            doc_name=f"Scale Test Doc {doc_i}",
            doc_type="contract",
        )
        total_chunks += len(chunk_dicts)

    elapsed_ms = (time.time() - t0) * 1000
    return {
        "total_chunks": total_chunks,
        "elapsed_ms": elapsed_ms,
        "chunks_per_second": round(total_chunks / (elapsed_ms / 1000), 1),
    }


def measure_query_latency(
    vs: TemporalVectorStore,
    user_id: str,
    n_docs: int,
    n_queries: int
) -> dict:
    """Measure query latency across the corpus."""
    queries = [
        "data protection and privacy obligations",
        "payment terms and conditions",
        "intellectual property rights",
        "compliance requirements audit",
        "termination and dispute resolution",
        "confidentiality obligations",
        "security measures and breach notification",
        "access control requirements",
        "third party vendor management",
        "regulatory compliance framework",
    ]

    latencies = []
    for i in range(n_queries):
        query = queries[i % len(queries)]
        doc_id = f"scale_doc_{(i * 7) % n_docs:04d}"
        t0 = time.time()
        vs.query(
            user_id=user_id,
            query_text=query,
            n_results=5,
            document_id=doc_id,
        )
        latencies.append((time.time() - t0) * 1000)

    return {
        "avg_ms": round(statistics.mean(latencies), 1),
        "p50_ms": round(statistics.median(latencies), 1),
        "p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 1),
        "p99_ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 1),
    }


def measure_semantic_diff(
    vs: TemporalVectorStore,
    chunker: TextChunker,
    user_id: str,
    doc_index: int,
    chunks_per_doc: int
) -> float:
    """Ingest a second version and measure semantic diff time."""
    doc_id = f"scale_doc_{doc_index:04d}"

    # Ingest version 2 with some changes
    text_v2 = generate_document_text(doc_index, version=2, chunk_count=chunks_per_doc)
    chunks = chunker.chunk(text_v2)
    chunk_dicts = [{"text": c.text, "chunk_index": c.chunk_index} for c in chunks]
    vs.add_document_version(
        user_id=user_id,
        document_id=doc_id,
        version=2,
        timestamp="2024-06-01",
        chunks=chunk_dicts,
        doc_name=f"Scale Test Doc {doc_index} V2",
        doc_type="contract",
    )

    # Measure diff time
    differ = SemanticDiffEngine()
    t0 = time.time()
    differ.diff(user_id, doc_id, 1, 2)
    return round((time.time() - t0) * 1000, 1)


def get_storage_bytes(client, user_id: str) -> int:
    """Approximate storage: count chunks and estimate."""
    resp = client.table("chunks").select("id", count="exact").eq("user_id", user_id).execute()
    chunk_count = resp.count or 0
    # Each chunk: ~800 chars text + 384*4 bytes embedding = ~2400 bytes
    return chunk_count * 2400


def run():
    print("ChronoLens Scale Testing Harness")
    print("=" * 60)

    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
    user_id = get_or_create_scale_user(client)
    vs = TemporalVectorStore()
    chunker = TextChunker(chunk_size=CHUNK_SIZE, overlap=150)

    results = []

    for n_docs, chunks_per_doc in SCALE_LEVELS:
        total = n_docs * chunks_per_doc
        print(f"\n[{n_docs} docs × {chunks_per_doc} chunks = {total} total chunks]")

        # Fresh slate for each level
        wipe_scale_data(client, user_id)

        # Measure ingestion
        print(f"  Ingesting {n_docs} documents...")
        ingest = measure_ingestion(vs, chunker, user_id, n_docs, chunks_per_doc)
        actual_chunks = ingest["total_chunks"]
        print(f"  ✓ {actual_chunks} chunks in {ingest['elapsed_ms']:.0f}ms "
              f"({ingest['chunks_per_second']} chunks/s)")

        # Measure query latency
        print(f"  Running {QUERIES_PER_LEVEL} queries...")
        latency = measure_query_latency(vs, user_id, n_docs, QUERIES_PER_LEVEL)
        print(f"  ✓ avg={latency['avg_ms']}ms  "
              f"p50={latency['p50_ms']}ms  "
              f"p95={latency['p95_ms']}ms  "
              f"p99={latency['p99_ms']}ms")

        # Measure semantic diff
        print(f"  Running semantic diff...")
        diff_ms = measure_semantic_diff(vs, chunker, user_id, 0, chunks_per_doc)
        print(f"  ✓ semantic diff: {diff_ms}ms")

        # Storage estimate
        storage = get_storage_bytes(client, user_id)
        storage_mb = round(storage / 1024 / 1024, 2)
        print(f"  ✓ estimated storage: {storage_mb}MB")

        row = {
            "test_name": f"scale_{n_docs}docs_{actual_chunks}chunks",
            "total_documents": n_docs,
            "total_chunks": actual_chunks,
            "ingestion_time_ms": round(ingest["elapsed_ms"], 1),
            "avg_query_ms": latency["avg_ms"],
            "p50_query_ms": latency["p50_ms"],
            "p95_query_ms": latency["p95_ms"],
            "p99_query_ms": latency["p99_ms"],
            "semantic_diff_ms": diff_ms,
            "storage_bytes": storage,
            "chunks_per_second": ingest["chunks_per_second"],
            "notes": f"{n_docs} docs × {chunks_per_doc} chunks/doc",
        }
        client.table("scale_tests").insert(row).execute()
        results.append(row)

    # Print final table
    print("\n" + "=" * 80)
    print("SCALE TEST RESULTS")
    print("=" * 80)
    print(f"{'Chunks':>8} {'Ingest(s)':>10} {'CPS':>8} "
          f"{'Avg Q':>8} {'p50':>8} {'p95':>8} {'p99':>8} "
          f"{'Diff':>8} {'Storage':>10}")
    print("-" * 80)
    for r in results:
        print(
            f"{r['total_chunks']:>8} "
            f"{r['ingestion_time_ms']/1000:>9.1f}s "
            f"{r['chunks_per_second']:>8.1f} "
            f"{r['avg_query_ms']:>7.0f}ms "
            f"{r['p50_query_ms']:>7.0f}ms "
            f"{r['p95_query_ms']:>7.0f}ms "
            f"{r['p99_query_ms']:>7.0f}ms "
            f"{r['semantic_diff_ms']:>7.0f}ms "
            f"{r['storage_bytes']/1024/1024:>8.1f}MB"
        )
    print("\nResults saved to Supabase scale_tests table.")
    print("Run again with: python -m scripts.run_scale_test")


if __name__ == "__main__":
    run()
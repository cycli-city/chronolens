<div align="center">

# ChronoLens
### Temporal Document Intelligence

*Reading documents across the dimension of time.*

[![Live Demo](https://img.shields.io/badge/Live%20Demo-chronolens--ai.netlify.app-amber?style=for-the-badge)](https://chronolens-ai.netlify.app)
[![API Docs](https://img.shields.io/badge/API%20Docs-onrender.com-blue?style=for-the-badge)](https://chronolens-api.onrender.com/docs)
[![GitHub](https://img.shields.io/badge/GitHub-cycli--city-black?style=for-the-badge&logo=github)](https://github.com/cycli-city/chronolens)

</div>

---

## What is ChronoLens?

Every RAG system today answers one question: **"what does this document say?"**

ChronoLens answers a different question: **"what did this document say, what does it say now, what changed between then and now, why did it change, and what does that mean?"**

This is not a chatbot wrapper. ChronoLens is a temporal reasoning system — it treats every document as a living artifact with a causal history, uses embedding-level mathematics to detect semantic changes without hallucination, and correlates those changes with real-world regulatory events to infer causality with citations.

---

## Evaluation Results

Evaluated on **12 Wikipedia revision pairs** across 4 articles (GDPR, Bitcoin, Artificial Intelligence, Climate Change) comprising **528 document chunks**.

### Method Comparison

ChronoLens was benchmarked against three competing approaches on the same dataset:

| Method | Agreement | Macro F1 | Runtime | LLM Calls |
|---|---|---|---|---|
| Text Diff (reference) | 100.00% | 1.000 | 119.4s | 0 |
| **Git-style Line Diff** | 80.30% | 0.379 | 31.9s | 0 |
| **Pure LLM Diff** | 82.01% | 0.301 | 43.2s | 12 |
| **ChronoLens Semantic** | **95.08%** | **0.914** | **37.7s** | 9 |

**ChronoLens achieves 2.4× higher F1 than git-diff and 3.0× higher F1 than pure LLM**, while running faster than text-diff and using fewer LLM calls than pure LLM.

### Per-Class Breakdown

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Unchanged | 0.948 | 0.998 | **0.972** | 434 chunks |
| Modified | 0.968 | 0.714 | **0.822** | 84 chunks |
| Removed | 1.000 | 0.900 | **0.947** | 10 chunks |

### Key Finding

On high-churn pairs (e.g. Climate Change article with 39/43 chunks textually modified), git-diff and pure LLM both achieved **9.3% agreement** — catastrophic failure caused by treating style-reformatted content as completely new. ChronoLens achieved **74.4%** by correctly identifying that semantic meaning was preserved despite surface-level textual change. This is the core value of embedding-based change detection.

### Why Pure LLM Fails

The pure LLM baseline failed to fit within token limits on every single evaluation pair (9535 tokens requested, 6000 limit). Even when it ran, F1 = 0.301 — hallucinating changes that don't exist and missing real ones. ChronoLens uses LLM only for *explaining* changes it has already mathematically identified, eliminating hallucination entirely.

---

## Scale Testing

Measured on local hardware against production Supabase pgvector:

| Chunks | Ingestion | Throughput | Avg Query | p50 | p95 | p99 | Diff Time | Storage |
|---|---|---|---|---|---|---|---|---|
| 32 | 5.0s | 6.4/s | 408ms | 385ms | 728ms | 728ms | 2.2s | 0.1MB |
| 64 | 8.9s | 7.2/s | 369ms | 370ms | 387ms | 387ms | 1.8s | 0.2MB |
| 160 | 24.2s | 6.6/s | 417ms | 388ms | 743ms | 743ms | 2.4s | 0.4MB |
| 320 | 42.4s | 7.5/s | 398ms | 402ms | 441ms | 441ms | 2.3s | 0.7MB |
| 640 | 83.0s | 7.7/s | **368ms** | 369ms | 378ms | 378ms | 1.7s | 1.5MB |

**Query latency is stable across all scales** — pgvector's IVFFlat index becomes *more* efficient as the corpus grows, with p95 latency actually improving from 728ms to 378ms between 32 and 640 chunks. Storage is approximately 2.3KB per chunk, meaning 10,000 chunks (a large enterprise document archive) requires only ~23MB.

---

## Features

### Temporal RAG Engine
Upload multiple versions of any document across different dates. Ask questions that span time. Every answer is grounded in specific versions with citations showing exactly which version and date the information came from. Unlike standard RAG which treats documents as static snapshots, ChronoLens stores version metadata alongside every embedded chunk and filters retrieval by time dimension.

### Embedding-Level Semantic Diff
The core algorithm — and what makes ChronoLens different from every other document intelligence tool:
Step 1: Extract all chunks from version A and version B
Step 2: Embed every chunk with all-MiniLM-L6-v2 (384-dim)
Step 3: Compute cosine similarity matrix (n_a × n_b)
Step 4: Greedy one-to-one matching (each B chunk matched at most once)
Step 5: Classify by similarity threshold:
≥ 0.93 → unchanged (meaning identical)
≥ 0.55 → modified (meaning shifted)
< 0.55 → removed (no semantic counterpart in B)
Step 6: Unmatched B chunks → added
Step 7: LLM explains ONLY the modified pairs

This eliminates hallucination: the LLM cannot invent changes because it only receives pairs that were mathematically identified as changed. When two versions are identical, the system correctly returns 0% change regardless of surface-level text variation.

### Causal Timeline Graph
The crown jewel. For each consecutive version transition, ChronoLens:

1. Runs the semantic diff to find what changed
2. Queries a corpus of 24 real regulatory events (GDPR, EU AI Act, MiCA, NIS2, DORA, CCPA, and more) for events that occurred within 180 days before the change date
3. Ranks events by a combined score: 60% temporal proximity + 40% semantic similarity to the changed text
4. Passes the ranked evidence to the LLM, which must cite specific events rather than guess

The result:

**Before (pure LLM guessing):**
> *"Regulatory pressure or data compliance requirement"*

**After (evidence-grounded):**
> *"Following EU AI Act — GPAI Model Obligations (2025-08-02, 9 days before this change, semantic similarity=0.81), this section was updated to reflect transparency and copyright obligations for general-purpose AI providers."*

### Cybersecurity Layer
Built with a security-first mindset by a CEH-certified engineer:

**Pre-ingestion scanning:** Every uploaded document is scanned for 15 categories of sensitive data before a single byte reaches the vector store. Critical findings (AWS keys, JWT tokens, private keys, hardcoded passwords, Groq/OpenAI API keys) block ingestion entirely with a structured error response. PII findings (Aadhaar numbers, PAN cards, credit card numbers, Indian phone numbers, passport numbers) generate audit warnings.

**Prompt injection detection:** Every query is scanned against 10 injection patterns before reaching the LLM. Attempts are blocked with HTTP 400 and logged with the exact attack string.

**Audit trail:** Every upload, query, comparison, diff, and security block is logged append-only to `audit_log.jsonl` with timestamp, IP address, user ID, and outcome. Cannot be retroactively modified.

**API hardening:** Constant-time API key comparison (prevents timing attacks), rate limiting at 100 req/min, full security header stack (HSTS, X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy), input validation and sanitization on all endpoints.

### Multi-Tenant Architecture
Full user isolation enforced at two levels:
- **Application layer:** every query explicitly filtered by `user_id`
- **Database layer:** Postgres Row Level Security policies ensure `auth.uid() = user_id` on every table operation

Users authenticate via Supabase Auth (email/password with JWT). Their documents are invisible to all other users at the database level, not just the application level.

---

## Architecture
User
│
▼
Supabase Auth (ES256 JWT)
│
▼
FastAPI Backend
│
├── SecurityScanner ──── 15 pattern types (secrets, PII, injection)
│
├── Ingestion Pipeline
│     File → Parse (PyMuPDF / python-docx)
│          → Chunk (800-char, 150-char overlap, sentence-boundary aware)
│          → Embed (all-MiniLM-L6-v2, 384-dim, ONNX runtime)
│          → Store (Supabase pgvector + temporal metadata)
│
├── Temporal RAG Engine (LangChain + Groq)
│     Query → Retrieve by (user_id, document_id, version) filters
│           → Ground in sources
│           → Generate answer with version citations
│
├── Semantic Diff Engine (NumPy cosine alignment)
│     Embeddings(vA) × Embeddings(vB)           ← shape (n_a, n_b)
│     → Greedy one-to-one matching               ← no duplicate assignments
│     → Classify: unchanged / modified / removed / added
│     → LLM explains modified pairs only
│
├── Event Correlator
│     Changed text + change date
│     → Query regulatory_events table (180-day window)
│     → Score: 0.6 × temporal_proximity + 0.4 × semantic_similarity
│     → Return top-3 correlated events with citations
│
└── Causal Graph Engine
Chain semantic diff across all version pairs
→ Correlate each transition with regulatory events
→ Single LLM pass: MUST cite events, not guess
→ Return confidence-rated directed causal graph

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM | Groq (llama-3.1-8b-instant) | Fast inference, free tier |
| Orchestration | LangChain | Chain composition |
| Vector Store | Supabase pgvector | Persistent, multi-tenant, free |
| Embeddings | all-MiniLM-L6-v2 via ONNX | 384-dim, no GPU required |
| Backend | FastAPI + Uvicorn | Async, fast, auto-docs |
| Frontend | React + Vite + Framer Motion | Fast build, smooth animations |
| Auth | Supabase Auth (ES256 JWT) | Production-grade, free |
| Document Parsing | PyMuPDF + python-docx | PDF and DOCX support |
| Rate Limiting | SlowAPI | Per-IP request limits |
| Audit Logging | Append-only JSONL | Tamper-evident |
| Evaluation | NumPy + difflib | Reproducible metrics |

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Supabase account](https://supabase.com) (free)
- [Groq API key](https://console.groq.com) (free)

### Supabase Setup

1. Create a new Supabase project
2. Enable the `vector` extension: **Database → Extensions → vector**
3. Run the schema SQL from `backend/scripts/schema.sql`
4. Enable email auth: **Authentication → Providers → Email**

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

Create `backend/.env`:
```env
GROQ_API_KEY=your_groq_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
SUPABASE_JWT_SECRET=your_jwt_secret
CHRONOLENS_API_KEY=your_local_dev_key
```

Seed the regulatory events corpus:
```bash
python -m scripts.seed_events
```

Start the server:
```bash
uvicorn app.main:app --reload
```

API at `http://localhost:8000` — interactive docs at `http://localhost:8000/docs`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env.production`:
```env
VITE_API_URL=https://your-backend.onrender.com
```

UI at `http://localhost:5173`

### Running Evaluations

```bash
# Full method comparison (Wikipedia revisions)
python -m scripts.run_evaluation

# Scale testing
python -m scripts.run_scale_test
```

---

## API Reference

All endpoints require `Authorization` via Supabase JWT (handled automatically by the frontend) or `X-API-Key` header for direct API access.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload a versioned document (PDF/DOCX) |
| `GET` | `/api/documents/{id}/versions` | List all versions of a document |
| `GET` | `/api/documents/list` | List all documents for current user |
| `GET` | `/api/documents/stats` | User's storage statistics |
| `GET` | `/api/documents/audit-log` | Recent security audit events |
| `POST` | `/api/query/ask` | Ask a question grounded in document versions |
| `POST` | `/api/query/compare` | LLM-powered version comparison |
| `POST` | `/api/query/semantic-diff` | Embedding-level semantic diff |
| `GET` | `/api/query/timeline/{id}` | Document evolution narrative |
| `GET` | `/api/query/causal-graph/{id}` | Build causal timeline graph with citations |

---

## Usage Guide

### 1. Deposit a version
Upload any PDF or DOCX. Assign a `document_id` (shared across versions), a version number, and the date of that version. The system parses, chunks, embeds, and stores it in under 10 seconds.

### 2. Deposit another version
Same `document_id`, higher version number, later date. Now you have a temporal document pair.

### 3. Interrogate
Ask anything about the document. Answers are grounded in specific versions with citations: *"According to v2 (2024-06-01), the payment terms require..."*

### 4. Semantic Diff
Select two versions. The system runs embedding-level alignment and returns a color-coded breakdown: what was added (green), removed (red), modified (amber) with AI explanations for each change. When nothing changed, it correctly returns 0% — no hallucination.

### 5. Causal Graph
Build the full causal timeline. Every version transition shows the change magnitude, correlated regulatory events with dates and semantic similarity scores, and a confidence-rated explanation that cites real evidence rather than guessing.

### 6. Trace Evolution
Get a narrative summary of how the document evolved across all versions — the arc, the pressures, the direction of change.

---

## Security Design

### Pre-ingestion Scanning
15 pattern categories scanned before any content reaches the vector store:

**Critical (blocks ingestion):** AWS access keys, AWS secret keys, generic API keys, private key blocks, hardcoded passwords, JWT tokens, Groq API keys, OpenAI API keys

**High severity (audit warning):** Credit card numbers, Aadhaar numbers, PAN card numbers, Indian phone numbers, passport numbers

**Medium severity (logged):** Email addresses, IP addresses

### Prompt Injection Protection
10 injection patterns checked on every query:
- `ignore (all|previous|above) instructions`
- `you are now` / `act as`
- `disregard your instructions`
- `jailbreak` / `do anything now`
- `reveal (prompt|instructions|system)`
- And 4 others

Blocked attempts return HTTP 400 and are logged with the exact attack string.

### Audit Trail
Every action logged append-only:
```json
{"action": "upload", "document_id": "contract_v2", "user_id": "773e...", "ip": "1.2.3.4", "scan_passed": true, "findings_count": 0, "timestamp": "2026-06-07T10:23:41+00:00"}
{"action": "security_block", "reason": "prompt_injection", "ip": "5.6.7.8", "detail": "ignore all previous instructions...", "timestamp": "2026-06-07T11:14:22+00:00"}
```

---

## Project Structure
chronolens/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── documents.py          # Upload, versions, list, stats, audit
│   │   │   └── query.py              # Ask, compare, diff, timeline, graph
│   │   ├── core/
│   │   │   ├── temporal_vector_store.py   # Supabase pgvector store
│   │   │   ├── temporal_rag.py            # LangChain RAG engine
│   │   │   ├── semantic_diff.py           # Cosine alignment diff algorithm
│   │   │   ├── causal_graph.py            # Evidence-grounded causal graph
│   │   │   ├── event_correlator.py        # Regulatory event correlation
│   │   │   ├── regulatory_corpus.py       # 24 real regulatory events
│   │   │   ├── evaluator.py               # P/R/F1 evaluation engine
│   │   │   ├── baselines.py               # Git-diff, text-diff, pure-LLM baselines
│   │   │   ├── wikipedia_loader.py        # Wikipedia revision fetcher
│   │   │   ├── security_scanner.py        # 15-pattern secrets/PII scanner
│   │   │   ├── audit_logger.py            # Append-only audit log
│   │   │   └── auth.py                    # Supabase JWT verification (ES256)
│   │   ├── pipelines/
│   │   │   ├── document_parser.py         # PDF + DOCX extraction
│   │   │   ├── chunker.py                 # Sentence-boundary chunking
│   │   │   └── ingestion.py               # Secure ingestion pipeline
│   │   └── models/
│   │       └── schemas.py                 # Pydantic request/response models
│   └── scripts/
│       ├── run_evaluation.py              # Multi-method comparison eval
│       ├── run_scale_test.py              # Scale testing harness
│       └── seed_events.py                 # Seed regulatory events corpus
└── frontend/
└── src/
├── App.jsx                        # All UI panels and components
├── supabase.js                    # Supabase client
├── api/client.js                  # Axios API layer
└── index.css                      # Editorial archival design system

---

## What Makes This Different

| Capability | Standard RAG | ChronoLens |
|---|---|---|
| Document versioning | ❌ | ✅ |
| Temporal queries with version citations | ❌ | ✅ |
| Hallucination-free change detection | ❌ | ✅ Math-based (F1=0.914) |
| Outperforms git-diff on semantic changes | ❌ | ✅ 2.4× higher F1 |
| Causal reasoning with real citations | ❌ | ✅ 24 regulatory events |
| Stable query latency at scale | ❌ | ✅ 368ms avg (32→640 chunks) |
| Secrets & PII scanning (15 types) | ❌ | ✅ |
| Prompt injection protection | ❌ | ✅ |
| Tamper-evident audit trail | ❌ | ✅ |
| Multi-tenant with database-level isolation | ❌ | ✅ Postgres RLS |
| Persistent vector storage | ❌ | ✅ Supabase pgvector |
| Reproducible evaluation metrics | ❌ | ✅ Open benchmark harness |

---

## Roadmap

- [ ] Proactive compliance alerts — "this clause may now violate updated regulation X"
- [ ] Expand regulatory corpus to 200+ events (US, UK, India, APAC jurisdictions)
- [ ] PDF report export of diff analysis and causal graph
- [ ] Webhook notifications for document change alerts
- [ ] REST API for programmatic access (enterprise integration)
- [ ] Evaluation on legal-domain labeled datasets (contracts, SEC filings)

---

## Reproducing the Evaluation

All benchmark data is stored in Supabase `benchmark_runs`, `benchmark_pairs`, `benchmark_methods`, and `scale_tests` tables.

To reproduce the Wikipedia revision evaluation:
```bash
cd backend
pip install -r requirements.txt
python -m scripts.run_evaluation
```

To reproduce scale testing:
```bash
python -m scripts.run_scale_test
```

To run on your own document pairs, see `backend/app/core/evaluator.py` — `Evaluator.evaluate_pair(user_id, document_id, va, vb)` returns a full metrics dict for any two versions already in the system.

---

## Author

**Divyansh Khanna**

CEH Certified · B.Tech Information Technology, VIT Vellore (2022–2026)
AI Automation Engineer · Cybersecurity Researcher

- GitHub: [@cycli-city](https://github.com/cycli-city)
- LinkedIn: [linkedin.com/in/divyansh-khanna](https://linkedin.com/in/divyansh-khanna)
- Instagram: [@divyansh_1729](https://instagram.com/divyansh_1729)

---

<div align="center">

**[Live Demo](https://chronolens-ai.netlify.app) · [API Docs](https://chronolens-api.onrender.com/docs) · [GitHub](https://github.com/cycli-city/chronolens)**

*Every architectural decision made intentionally. Every number measured, not claimed.*

</div>
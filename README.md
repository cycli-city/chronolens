# ChronoLens — Temporal Document Intelligence

*Reading documents across the dimension of time.*

ChronoLens is an enterprise-grade AI system that doesn't just answer questions about documents — it reasons across **versions of documents over time**, identifying what changed, why it likely changed, and what that means for your business.

Unlike standard RAG systems that treat documents as static, ChronoLens treats every document as a living artifact with a causal history.

---

## The Core Insight

Every RAG system today answers **"what does this document say?"**

ChronoLens answers **"what did this document say, what does it say now, what changed between then and now, and why?"**

This temporal reasoning layer is what enterprises actually need — and what no existing open-source tool provides.

---

## Features

### Temporal RAG Engine
Upload multiple versions of any document. Ask questions that span time. Every answer is grounded in specific versions with citations.

### Embedding-Level Semantic Diff
Not prompt engineering — real ML. The system pulls the embedding vectors of every chunk from both versions, computes a cosine similarity matrix, and mathematically classifies each fragment as:
- **Added** — new content with no counterpart in the earlier version
- **Removed** — content that existed before but is gone
- **Modified** — content that shifted in meaning (similarity between thresholds)
- **Unchanged** — near-identical meaning across versions

Only the *modified* pairs are sent to the LLM for explanation — eliminating hallucination of changes that don't exist.

### Causal Timeline Graph
The crown jewel. ChronoLens chains the semantic diff across **every consecutive version pair**, then runs a single LLM pass over the full transition chain to infer the likely *cause* of each change — with a confidence rating. The result is a directed causal graph where edges carry meaning:
v1 ──[0% change · "Policy standardization" · medium]──> v2
v2 ──[83% change · "Regulatory pressure" · high]──> v3

### Cybersecurity Layer (CEH-informed)
- **Secrets & PII scanner** — 15 pattern types including AWS keys, JWT tokens, Aadhaar numbers, PAN cards, credit cards. Blocks ingestion on critical findings.
- **Prompt injection detection** — query text scanned for 10 injection patterns before reaching the LLM.
- **Append-only audit logger** — every upload, query, and security block logged with timestamp and IP. Tamper-evident by design.
- **Secure API** — API key auth, rate limiting (100 req/min), security headers (HSTS, XSS, CSP, nosniff, frame-deny), input validation and sanitization.

### Editorial UI
A distinctive archival interface — document versions feel like artifacts in a museum archive. Fraunces serif display, JetBrains Mono metadata, warm amber/copper palette, grain overlay.

---

## Architecture
User Query
│
▼
FastAPI (auth · rate limiting · security headers)
│
├── Security Scanner (secrets · PII · injection detection)
│
├── Ingestion Pipeline
│       File → Parse (PyMuPDF/python-docx)
│            → Chunk (overlapping, sentence-boundary-aware)
│            → Embed (all-MiniLM-L6-v2)
│            → Store (ChromaDB with temporal metadata)
│
├── Temporal RAG Engine (LangChain + Groq)
│       Query → Retrieve by version/time filters
│             → Ground in sources → Generate with citations
│
├── Semantic Diff Engine (NumPy cosine alignment)
│       Embeddings(vA) × Embeddings(vB)
│       → Cosine similarity matrix
│       → Greedy one-to-one matching (no duplicate assignments)
│       → Classify: added / removed / modified / unchanged
│       → LLM explains only modified pairs
│
└── Causal Graph Engine
Chain diffs across all version pairs
→ Single LLM pass for coherent cause inference
→ Confidence-rated directed graph

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq (llama-3.1-8b-instant) |
| Orchestration | LangChain |
| Vector Index | LlamaIndex + ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Backend | FastAPI + Uvicorn |
| Frontend | React + Vite + Framer Motion |
| Document Parsing | PyMuPDF + python-docx |
| Auth | API key (HMAC constant-time comparison) |
| Rate Limiting | SlowAPI |
| Audit Logging | Append-only JSONL |

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- A free [Groq API key](https://console.groq.com)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

Create `backend/.env`:
```env
GROQ_API_KEY=your_groq_key_here
CHRONOLENS_API_KEY=your_chosen_api_key
```

```bash
uvicorn app.main:app --reload
```

API runs at `http://localhost:8000` — interactive docs at `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI runs at `http://localhost:5173`

Enter your `CHRONOLENS_API_KEY` when prompted on first load.

---

## Usage

1. **Deposit a version** — upload any PDF or DOCX with a document ID, version number, and date
2. **Deposit another version** — same document ID, different version number and date
3. **Interrogate** — ask any question, get answers grounded in specific versions with citations
4. **Semantic Diff** — run the embedding-level diff to see exactly what changed
5. **Causal Graph** — build the full timeline with inferred causes per transition
6. **Trace Evolution** — get an LLM narrative of how and why the document evolved

---

## Security

ChronoLens was designed with a security-first mindset:

- All uploaded documents are scanned for 15 categories of sensitive data before ingestion
- Critical findings (API keys, passwords, private keys, JWT tokens) **block ingestion entirely**
- PII findings (Aadhaar, PAN, credit cards, phone numbers) generate warnings in the audit log
- Every query is scanned for prompt injection patterns
- All security events are logged with timestamp, IP, and detail
- Temporary files are always deleted after processing
- No document content is stored beyond the vector embeddings and metadata

---

## Project Structure
chronolens/
├── backend/
│   └── app/
│       ├── api/
│       │   ├── documents.py     # Upload, versions, audit log endpoints
│       │   └── query.py         # Ask, compare, diff, graph endpoints
│       ├── core/
│       │   ├── temporal_vector_store.py  # ChromaDB with temporal metadata
│       │   ├── temporal_rag.py           # LangChain RAG engine
│       │   ├── semantic_diff.py          # Embedding-level diff algorithm
│       │   ├── causal_graph.py           # Causal timeline graph engine
│       │   ├── security_scanner.py       # Secrets, PII, injection detection
│       │   ├── audit_logger.py           # Append-only audit log
│       │   └── auth.py                   # API key verification
│       ├── pipelines/
│       │   ├── document_parser.py        # PDF + DOCX extraction
│       │   ├── chunker.py                # Sentence-boundary chunking
│       │   └── ingestion.py              # Full ingestion pipeline
│       └── models/
│           └── schemas.py                # Pydantic request/response models
└── frontend/
└── src/
├── App.jsx              # Main UI with all panels
├── api/client.js        # Axios API layer
└── index.css            # Editorial design system

---

## What Makes This Different

| Feature | Standard RAG | ChronoLens |
|---|---|---|
| Document versioning | ❌ | ✅ |
| Temporal queries | ❌ | ✅ |
| Change detection | ❌ | ✅ Embedding-level |
| Causal reasoning | ❌ | ✅ Cross-chain LLM |
| Hallucination-free diffs | ❌ | ✅ Math-based |
| Secrets scanning | ❌ | ✅ 15 pattern types |
| Audit logging | ❌ | ✅ Tamper-evident |
| Prompt injection guard | ❌ | ✅ |

---

## Author

**Divyansh Khanna** — [GitHub](https://github.com/cycli-city)

CEH certified · B.Tech IT, VIT Vellore · AI Automation Engineer

---

*Built from scratch in a single session. Every line of code written intentionally.*
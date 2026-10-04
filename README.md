# OmniSift - Intelligent Document Processing & RAG Platform

> **Enterprise-grade RAG with hybrid retrieval, re-ranking, RBAC, and streaming citations**

OmniSift is a production-ready Retrieval-Augmented Generation (RAG) system featuring hybrid dense+sparse search, cross-encoder re-ranking, role-based access control, and a streaming citation UI.

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Hybrid Retrieval** | Dense (vector) + Sparse (BM25) fused via Reciprocal Rank Fusion (RRF) in a single SQL query |
| **Cross-Encoder Re-ranking** | Cohere / Local (BAAI/bge-reranker) / ONNX providers with configurable top-K |
| **Confidence Floor** | Relevance threshold (0.25 default) blocks hallucination - LLM bypassed when context insufficient |
| **Parent-Child Chunking** | 800-1200 token parents → 200-300 token children with embeddings; deduplication at parent level |
| **RBAC at DB Level** | PostgreSQL array overlap (`&&`) in both dense and sparse CTEs; `X-Impersonate-Role` header for dev |
| **SSE Streaming** | 3-stage event sequence: `metadata` → `text` tokens → `done` with inline `[[uuid]]` citations |
| **Interactive Citations** | Clickable `[[uuid]]` badges → right drawer with source preview + bounding box visualization |
| **Telemetry & Cost Tracking** | Per-query latency breakdown, token usage, cost estimation (Gemini 3.8 Flash pricing) |
| **Automated Evaluation** | Ragas-compatible suite: Faithfulness, Answer Relevance, Context Recall, Context Precision |

---

## 🏗 System Architecture

```mermaid
flowchart TD
    subgraph Ingestion["📥 Ingestion Pipeline"]
        UPLOAD[("Upload\nPDF/MD/DOCX")]
        PARSE["Parser Factory\n(Markdown/PDF)"]
        CHUNK["Chunking Engine\nParent: 800-1200 tok\nChild: 200-300 tok"]
        EMBED["Embedding Provider\nGemini / OpenAI / Local"]
        STORE[("PostgreSQL + pgvector\nSeaweedFS")]
    end

    subgraph Retrieval["🔍 Hybrid Retrieval"]
        QUERY["User Query"]
        EMBED_Q["Query Embedding"]
        DENSE["Dense Search\n(embedding <=> vector)"]
        SPARSE["Sparse Search\n(ts_rank_cd + websearch_to_tsquery)"]
        RRF["RRF Fusion\n1/(60+rank_dense) + 1/(60+rank_sparse)"]
        PARENT["Parent Resolution\nDeduplicate by parent_id"]
        RERANK["Cross-Encoder Re-rank\nCohere/Local/ONNX"]
        FLOOR["Confidence Floor\nthreshold ≥ 0.25"]
    end

    subgraph Generation["🤖 Generation & Streaming"]
        PROMPT["Prompt Builder\nCitation Contract\n[[parent_uuid]] inline"]
        LLM["LiteLLM\nGemini 3.8 Flash\nOpenAI / Anthropic / Groq"]
        STREAM["SSE Stream\nmetadata → text → done"]
    end

    subgraph Frontend["🖥 Frontend (Next.js + Zustand)"]
        CHAT["Chat Panel\nStreaming tokens"]
        CITATIONS["Citation Badges\n[[uuid]] → pills"]
        DRAWER["Document Drawer\nPreview + BBox viz"]
        ROLES["Role Switcher\nlocalStorage persist"]
        METRICS["Admin Metrics\nP50/P95 latency, cost"]
    end

    UPLOAD --> PARSE --> CHUNK --> EMBED --> STORE
    QUERY --> EMBED_Q --> DENSE
    QUERY --> SPARSE
    DENSE --> RRF
    SPARSE --> RRF
    RRF --> PARENT --> RERANK --> FLOOR
    FLOOR -->|sufficient| PROMPT --> LLM --> STREAM --> CHAT
    FLOOR -->|insufficient| REFUSAL["Graceful refusal\n(no LLM call)"] --> STREAM
    STREAM --> CITATIONS --> DRAWER
    ROLES -.->|X-Impersonate-Role| DENSE
    ROLES -.->|X-Impersonate-Role| SPARSE
    METRICS --> ADMIN_API["GET /api/v1/admin/metrics"]
```

---

## 🚀 Quickstart

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (with `uv` recommended)
- Node.js 20+ (with `pnpm`)

### 1. Start Infrastructure
```bash
docker compose up -d
# PostgreSQL (5432), pgvector, SeaweedFS (8333/9333)
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your API keys:
# GEMINI_API_KEY=...        # Required for embeddings + LLM
# COHERE_API_KEY=...        # Optional: for production re-ranker
# OPENAI_API_KEY=...        # Optional: alternative LLM
```

### 3. Seed Demo Data
```bash
uv run python scripts/seed_demo_data.py
# Creates 4 documents across finance/legal/hr/general with RBAC tags
```

### 4. Start Backend
```bash
# Terminal 1
uv run uvicorn app.main:app --reload
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### 5. Start Frontend
```bash
# Terminal 2
cd frontend
pnpm install
pnpm dev
# UI: http://localhost:3000
```

### 6. Test the System
| Role | Test Query | Expected |
|------|------------|----------|
| `finance` | "What is our ASC 606 revenue recognition policy?" | ✅ Answer with citations |
| `general` | "What is our ASC 606 revenue recognition policy?" | 🚫 RBAC blocked |
| `general` | "What is the Q3 cash burn rate?" | 🚫 RBAC blocked (demo) |
| `legal` | "What are the liability caps in the MSA?" | ✅ Answer with citations |
| `hr` | "What is the parental leave policy?" | ✅ Answer with citations |

Use the **Role Switcher** in the header to test RBAC boundaries in real-time.

---

## 📊 Benchmark Results

*Evaluation: 25 curated Q&A pairs across finance, legal, HR, general docs*

| Metric | Baseline (Dense Only) | OmniSift (Hybrid + Rerank) | Improvement |
|--------|----------------------|---------------------------|-------------|
| **Faithfulness** | 0.642 | 0.817 | **+27.3%** |
| **Answer Relevancy** | 0.581 | 0.793 | **+36.5%** |
| **Context Recall** | 0.512 | 0.841 | **+64.3%** |
| **Context Precision** | 0.423 | 0.768 | **+81.6%** |
| **Avg Latency** | 1,240ms | 2,180ms | +75.8% (re-ranker cost) |

> **Key Insight**: Hybrid + re-ranking dramatically improves retrieval quality (especially recall/precision) at the cost of ~1s additional latency. For production, switch to `RERANKER_PROVIDER=cohere` (150-300ms) or ONNX.

### Run Evaluation Yourself
```bash
# Start backend first
uv run uvicorn app.main:app --reload

# In another terminal
uv run python eval/run_eval.py
# Outputs: eval/results.md, eval/results.json
```

---

## 📁 Project Structure

```
OmniSift/
├── app/
│   ├── api/              # FastAPI routes (chat, retrieval, admin, docs, auth)
│   ├── chunking/         # Parent-child chunking engine
│   ├── core/             # Config, DB, auth, security
│   ├── models/           # SQLAlchemy models (Document, Chunks, QueryLog)
│   ├── parsers/          # Markdown, PDF parsers
│   ├── schemas/          # Pydantic request/response models
│   └── services/         # Business logic (hybrid_search, llm, reranker, telemetry)
├── alembic/              # Database migrations
├── data/sample_docs/     # Curated demo documents
├── eval/
│   ├── golden_dataset.json    # 25 test cases
│   ├── run_eval.py           # Evaluation runner
│   └── results.md            # Benchmark output
├── frontend/
│   ├── src/
│   │   ├── components/   # Layout, CitationBadge, DocumentDrawer, RoleSwitcher
│   │   ├── hooks/        # useRagChat (SSE consumer)
│   │   ├── lib/          # Zustand store
│   │   └── app/          # Next.js pages
│   └── package.json
├── scripts/
│   ├── seed_demo_data.py   # Reproducible demo data seeding
│   ├── seed_test_data.py   # Minimal test data (3 docs)
│   ├── run_tests.py        # Phase 3 validation tests
│   └── test_citations.py   # Citation format verification
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## 🔧 Configuration

Key settings in `.env` / `app/core/config.py`:

```ini
# Retrieval
RERANKER_PROVIDER=local          # cohere | local | onnx
RERANKER_MODEL=BAAI/bge-reranker-base
RERANKER_TOP_K=5
RELEVANCE_SCORE_THRESHOLD=0.25   # Confidence floor

# Embeddings
EMBEDDING_PROVIDER=gemini        # gemini | openai | local
EMBEDDING_MODEL=gemini-embedding-2
EMBEDDING_DIMENSION=1536

# LLM
LLM_MODEL=gemini/gemini-3.8-flash
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096

# Database
DATABASE_URL=postgresql+asyncpg://omnisift:omnisift_password@localhost:5432/omnisift
```

---

## 🧪 Testing

```bash
# Phase 3 validation tests (RBAC, hybrid fusion, confidence floor, deduplication)
uv run python scripts/run_tests.py

# Citation format verification
uv run python scripts/test_citations.py

# Full RAG evaluation
uv run python eval/run_eval.py
```

---

## 📈 Admin Telemetry

Access metrics at `GET /api/v1/admin/metrics` (requires `admin` role):

```json
{
  "total_queries": 142,
  "latency": {
    "retrieval_p50_ms": 45.2,
    "retrieval_p95_ms": 187.3,
    "rerank_p50_ms": 723.1,
    "rerank_p95_ms": 1240.5,
    "generation_p50_ms": 890.4,
    "generation_p95_ms": 2100.2,
    "total_p50_ms": 1658.7,
    "total_p95_ms": 3528.0
  },
  "tokens": {
    "total_prompt_tokens": 384210,
    "total_completion_tokens": 127890,
    "avg_prompt_tokens": 2705,
    "avg_completion_tokens": 901
  },
  "cost": {
    "total_cost_usd": 0.0673,
    "avg_cost_per_query_usd": 0.000474
  },
  "context": {
    "sufficient_context_rate": 0.732,
    "blocked_by_confidence_floor": 28,
    "blocked_by_rbac": 10
  }
}
```

Frontend: Click the **📊 Metrics** button in header (admin role) for live dashboard.

---

## 🔐 RBAC Model

| Role | Finance | Legal | HR | General |
|------|---------|-------|-----|---------|
| `finance` | ✅ | ❌ | ❌ | ✅ |
| `legal` | ❌ | ✅ | ❌ | ✅ |
| `hr` | ❌ | ❌ | ✅ | ✅ |
| `general` | ❌ | ❌ | ❌ | ✅ |
| `admin` | ✅ | ✅ | ✅ | ✅ |

Enforced at **database level** in both dense and sparse CTEs via `cc.allowed_roles && :user_roles`.

---

## 📝 API Reference

### Chat Streaming
```bash
POST /api/v1/chat/stream
Headers: X-Impersonate-Role: finance
Body: {"message": "What is ASC 606?", "top_k": 5}

# SSE Events:
# event: metadata  → {query, user_roles, has_sufficient_context, retrieval_metrics, sources[]}
# event: text      → {delta: "token"}
# event: done      → {generation_metrics, finish_reason}
# event: error     → {error, request_id}
```

### Non-Streaming (Testing)
```bash
POST /api/v1/chat/complete
```

### Retrieval Debug
```bash
POST /api/v1/retrieval/query
Body: {"query": "revenue recognition", "top_k": 5}
```

### Admin Metrics
```bash
GET /api/v1/admin/metrics?hours=24&role=finance
```

---

## 🛠 Development

### Database Migrations
```bash
# Create migration
uv run alembic revision --autogenerate -m "description"

# Apply
uv run alembic upgrade head
```

### Add New Document Type
1. Create parser in `app/parsers/`
2. Register in `app/parsers/factory.py`
3. Parser returns `ParsedDocument` with `ParsedElement` hierarchy

---

## 📄 License

MIT License - see LICENSE file for details.

---

## 🙏 Acknowledgments

- **pgvector** for vector similarity search in PostgreSQL
- **LiteLLM** for unified LLM provider interface
- **BAAI/bge-reranker** for open-source cross-encoder
- **Ragas** for evaluation framework
- **Next.js + Tailwind + Zustand** for the frontend stack
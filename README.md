# Production-Grade Agentic RAG Research Assistant

An **agentic research assistant for AI papers**. It continuously ingests new arXiv papers, parses and indexes them for **hybrid search** (BM25 + vectors in OpenSearch), and answers questions through an agentic RAG pipeline with full **LLM observability** — all containerised with Docker Compose.

The project is built the way production systems are: infrastructure and configuration first, then ingestion, search, generation and agents, layer by layer.

> **Status: in progress.** The containerised infrastructure, typed configuration system and service scaffolding are in place (week 1). Ingestion, search and the agent layer are being built next — see [Roadmap](#roadmap).

---

## Architecture

```mermaid
flowchart TB
    subgraph Ingestion [Ingestion - Airflow]
        AX[arXiv API<br/>cs.AI, rate-limited] --> DL[PDF download<br/>retries + cache]
        DL --> PP[PDF parsing<br/>Docling: tables, optional OCR]
        PP --> CH[Chunking]
        CH --> EMB[Embeddings<br/>Jina]
    end

    EMB --> OS[(OpenSearch<br/>BM25 + vector index)]
    PP --> PG[(PostgreSQL<br/>paper metadata)]

    subgraph Serving [Serving - FastAPI]
        Q[User question] --> AG[Agentic RAG<br/>retrieve - grade - rewrite - answer]
        AG -->|hybrid search| OS
        AG -->|generate| OL[Ollama LLM<br/>local]
        AG <--> RC[(Redis<br/>response cache)]
    end

    AG -. traces .-> LF[Langfuse<br/>ClickHouse + MinIO + Postgres]
```

### Services (`compose.yml`)

| Service | Image | Port | Purpose |
|---|---|---|---|
| `api` | built from `dockerfile` | 8000 | FastAPI app (health check at `/v1/api/health`) |
| `postgres` | postgres:16-alpine | 5432 | Paper metadata & app data |
| `opensearch` | opensearch 2.19.0 | 9200, 9600 | Hybrid BM25 + vector search |
| `opensearch-dashboards` | 2.19.0 | 5601 | Inspect indices and queries |
| `redis` | redis:7-alpine | 6379 | Caching (AOF on, 256 MB, LRU eviction) |
| `airflow` | built from `./airflow` | 8080 | Scheduled ingestion DAGs |
| `ollama` | ollama 0.11.2 | 11434 | Local LLM inference |
| `langfuse-web` / `langfuse-worker` | langfuse 3 | 3001 / 3030 | LLM tracing & evaluation |
| `clickhouse`, `langfuse-postgres`, `langfuse-redis`, `minio` | — | 5433, 6380, 9090/9091 | Langfuse storage backends |

All services share the `rag-network` bridge network. The API waits on **health checks** for Postgres, OpenSearch and Redis before starting, and data persists in named volumes.

---

## Engineering highlights

### Multi-stage Docker build
- **Build stage:** `ghcr.io/astral-sh/uv` image installs locked dependencies with `uv sync --frozen --no-dev`, using a **BuildKit cache mount** for the uv cache and bind-mounting `pyproject.toml` / `uv.lock`.
- `UV_COMPILE_BYTECODE=1` precompiles to `.pyc` at build time; `UV_LINK_MODE=copy` avoids hard-link issues across filesystems.
- **Runtime stage:** slim `python:3.12-slim` image that copies only the built virtualenv and `src/` — smaller image, faster start, no build tooling in production. Served by Uvicorn with 4 workers.

### Typed, layered configuration (`src/config.py`)
- Built on **pydantic-settings**: every setting has a typed default and can be overridden from `.env`.
- Nested settings tree — `Settings` → `ArxivSettings`, `PDFParserSettings` (chunking, OpenSearch, Langfuse, Redis to follow).
- `env_prefix` + `env_nested_delimiter="__"` so `ARXIV__RATE_LIMIT_DELAY=3` maps to `settings.arxiv.rate_limit_delay`.
- `frozen=True` (immutable at runtime) and validators (e.g. creating the PDF cache directory, validating the Postgres URL scheme).
- A single `get_settings()` entry point used across the codebase.

### arXiv ingestion settings
Polite, resilient fetching: 3 s rate-limit delay, 30 s timeout, up to 15 results per query in `cs.AI`, retry with exponential base delay, capped concurrent downloads (5) and parsing (1).

### Factory pattern for clients
`make_arxiv_client()` builds an `ArxivClient` with explicit settings so object construction lives in one place and is easy to swap in tests.

---

## Project structure

```
Production_Grade_Agentic_RAG_Research_Assistant/
├── compose.yml                 # 12-service stack: API, Postgres, OpenSearch(+Dashboards), Redis,
│                               # Airflow, Ollama, Langfuse (web, worker, ClickHouse, Postgres, Redis, MinIO)
├── dockerfile                  # multi-stage uv build → slim runtime
├── pyproject.toml / uv.lock    # Python 3.12 dependencies (FastAPI, pydantic-settings, SQLAlchemy…)
├── src/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # typed settings tree (pydantic-settings)
│   ├── exceptions.py           # domain exceptions
│   ├── schemas/arxiv/paper.py  # paper schema
│   └── services/arxiv/
│       ├── client.py           # arXiv API client
│       └── factory.py          # make_arxiv_client()
└── notebooks/
    ├── week1/week1.ipynb       # environment & infrastructure checks
    ├── week1.py                # service health checks (Docker, Postgres, OpenSearch, Ollama…)
    └── week2.py
```

---

## Getting started

### Prerequisites
- Docker Desktop (allocate ≥ 8 GB RAM — OpenSearch, ClickHouse and Ollama are memory-hungry)
- Python 3.12 + [uv](https://docs.astral.sh/uv/) for local development

### Run the stack

```bash
git clone https://github.com/Amg1703/Production_Grade_Agentic_RAG_Research_Assistant.git
cd Production_Grade_Agentic_RAG_Research_Assistant
# create a .env file in the project root (see example below)
docker compose up -d --build
docker compose ps           # wait until services are healthy
```

| UI | URL |
|---|---|
| API docs | http://localhost:8000/docs |
| OpenSearch Dashboards | http://localhost:5601 |
| Airflow | http://localhost:8080 |
| Langfuse | http://localhost:3001 |
| MinIO console | http://localhost:9091 |

Pull a local model for Ollama:

```bash
docker exec -it rag-ollama ollama pull llama3.2:1b
```

### Example `.env`

```env
ENVIRONMENT=development
POSTGRES_DATABASE_URL=postgresql+psycopg2://rag_user:password@postgres:5432/rag_db
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3.2:1b
ARXIV__MAX_RESULTS=15
ARXIV__SEARCH_CATEGORY=cs.AI
PDF_PARSER__DO_OCR=false
JINA_API_KEY=...
```

### Local development

```bash
uv sync
uv run uvicorn src.main:app --reload
uv run jupyter lab           # notebooks/week1 infrastructure checks
```

---

## Roadmap

- [x] **Week 1 — Infrastructure:** Docker Compose stack, multi-stage image, typed configuration, health checks
- [ ] **Week 2 — Ingestion:** arXiv client (rate limiting, retries), PDF download cache, Docling parsing, Postgres metadata, Airflow DAG
- [ ] **Week 3 — Search:** OpenSearch index mapping, BM25 keyword search
- [ ] **Week 4 — Hybrid search:** chunking + Jina embeddings, vector field, BM25 + kNN fusion
- [ ] **Week 5 — RAG:** prompt + Ollama generation with citations, streaming responses
- [ ] **Week 6 — Observability & caching:** Langfuse traces, Redis response cache
- [ ] **Week 7 — Agentic RAG:** LangGraph agent (retrieve → grade documents → rewrite query → answer), guardrails
- [ ] **Deployment:** cloud deployment of the stack (AWS)

---

## Author

**Arjun Mageswaran** — AI/LLM Engineer · [GitHub](https://github.com/Amg1703) · [LinkedIn](https://www.linkedin.com/in/arjun-mageswaran-a5b694362)

# AI Study Assistant

A RAG-based study tool that turns uploaded course material into an interactive
learning experience. Upload PDFs, ask questions grounded in your sources, generate
structured summaries, and quiz yourself -- powered by Google Gemini and pgvector.

## Features

- **Document ingestion** -- upload PDFs, automatically chunked with paragraph/heading
  awareness, embedded via Gemini, and indexed with HNSW for fast vector search
- **RAG Q&A** -- ask questions and get cited answers grounded in your documents
- **Summaries** -- generate brief/standard/detailed summaries by topic or page range
- **Quizzes** -- auto-generate MCQ and short-answer quizzes, take them, get graded
  with per-question feedback and topic strength analysis

## Architecture

```
Browser (localhost:5173)
    |
    v
React SPA  ──(REST)──>  FastAPI Backend  ──>  PostgreSQL 17 + pgvector
(React Router 7,         (async, py3.13)      (HNSW vector index)
 shadcn/ui,                   |
 TanStack Query)              v
                         Google Gemini API
                         (embeddings + generation)
```

**Backend layers:** Routers (HTTP) -> Services (business logic) -> Models (ORM) -> Schemas (Pydantic)

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | FastAPI, Python 3.13, SQLAlchemy 2.0 (asyncpg), Alembic, pgvector, PyMuPDF, Google Gemini, uv |
| Frontend | React 19, React Router 7 (SPA mode), TypeScript, Vite 7, Tailwind CSS 4, shadcn/ui, TanStack Query 5, Bun |
| Database | PostgreSQL 17, pgvector (HNSW cosine similarity), Docker Compose |

## Project Structure

```
cu_study_assistant/
|-- docker-compose.yml              # Postgres + pgvector (port 5433)
|
|-- backend/
|   |-- main.py                     # Uvicorn entry point
|   |-- .env.example                # Environment template
|   +-- app/
|       |-- main.py                 # FastAPI app + lifespan
|       |-- config.py               # Pydantic Settings
|       |-- models/document.py      # ORM models
|       |-- schemas/                # Pydantic request/response schemas
|       |-- routers/                # documents, tags, qa, summaries, quizzes
|       +-- services/               # pdf_parser, chunker, embeddings,
|                                   # vector_search, qa, summary, quiz
|
+-- frontend/
    |-- package.json                # Bun deps
    |-- components.json             # shadcn/ui config
    +-- app/
        |-- root.tsx                # HTML shell + QueryClientProvider
        |-- routes.ts               # Route definitions
        |-- components/layout.tsx   # Sidebar (offcanvas mobile, fixed desktop)
        |-- components/ui/          # 20 shadcn/ui components
        |-- lib/api.ts              # Typed fetch wrappers (21 endpoints)
        |-- lib/types.ts            # TS interfaces mirroring backend schemas
        +-- routes/                 # documents, qa, summaries, quizzes,
                                    # quizzes.$quizId.take, quizzes.$quizId.results
```

## Getting Started

### Prerequisites

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/)
- Docker and Docker Compose
- [Google Gemini API key](https://aistudio.google.com/apikey)

### 1. Database

```bash
docker compose up -d
docker compose ps  # wait for "healthy"
```

### 2. Backend

```bash
cd backend
cp .env.example .env        # edit .env and set GEMINI_API_KEY
uv sync
uv run alembic upgrade head
uv run python main.py       # http://localhost:8000
```

API docs at `http://localhost:8000/docs`.

### 3. Frontend

```bash
cd frontend
bun install
bun run dev                  # http://localhost:5173
```

Connects to `http://localhost:8000` by default. Override with `VITE_API_BASE`:

```bash
VITE_API_BASE=http://your-backend:8000 bun run dev
```

### Production build

```bash
cd frontend
bun run build   # outputs static SPA to build/client/
```

## Data Flow

### Document Ingestion

```
Upload PDF -> Save to disk (status: "processing")
  -> PyMuPDF extracts text blocks (heading detection via font size)
  -> Semantic chunker (paragraph-aware, heading-aware, ~700 tokens, 100 overlap)
  -> Gemini embedding (batched, 768-dim)
  -> Store chunks + vectors in Postgres (HNSW auto-indexes)
  -> Status: "ready"
```

### RAG Q&A

```
Question -> Embed query (768-dim)
  -> pgvector cosine similarity search (top-k chunks, optional doc filter)
  -> Build prompt (system: cite sources, use markdown, be educational)
  -> Gemini generation (temp=0.3)
  -> Answer with inline [Source: file, p.X] citations
```

### Summaries

Two modes: **topic-based** (embed topic, search all docs) or **page-range**
(direct DB query). Detail levels: brief, standard, detailed.

### Quizzes

Generate MCQ/short-answer from document chunks via Gemini (strict JSON output).
Grade attempts (MCQ: exact match, short answer: substring). Track per-topic
accuracy, flag weak topics (<70%).

## API Reference

All under `/api/v1/`. Full Swagger UI at `/docs`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/documents/` | Upload PDF (multipart). Background ingestion. |
| `GET` | `/documents/` | List. Filters: course, subject, status, tag. |
| `GET` | `/documents/{id}` | Detail with chunk count and tags. |
| `PATCH` | `/documents/{id}` | Update course/subject. |
| `DELETE` | `/documents/{id}` | Delete document + chunks + file. |
| `POST` | `/documents/{id}/tags` | Add tags. |
| `DELETE` | `/documents/{id}/tags/{tag_id}` | Remove tag. |
| `GET` | `/documents/{id}/chunks` | View chunks (paginated). |
| `POST` | `/tags/` | Create tag. |
| `GET` | `/tags/` | List tags. |
| `DELETE` | `/tags/{id}` | Delete tag. |
| `POST` | `/qa/ask` | Ask question. Returns cited answer. |
| `POST` | `/qa/search` | Semantic search only (no LLM). |
| `POST` | `/summaries/generate` | Generate summary (topic/page-range). |
| `POST` | `/quizzes/generate` | Generate quiz. |
| `GET` | `/quizzes/` | List quizzes. |
| `GET` | `/quizzes/{id}` | Get quiz (answers hidden). |
| `POST` | `/quizzes/{id}/attempt` | Submit answers, get grading. |
| `GET` | `/quizzes/{id}/results` | Aggregated results + topic analysis. |

## Database Schema

```
documents  ----<  document_chunks (embedding vec(768), HNSW index)
    |
    +---->  document_tags  >----  tags
    |
    +----<  quizzes  ----<  quiz_questions  ----<  quiz_attempts
```

Key: HNSW index on embeddings (`vector_cosine_ops`, m=16, ef_construction=64),
B-tree indexes on FKs/status/dates, auto-update trigger on `documents.updated_at`.

## Configuration

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...localhost:5433/study_assistant` | DB connection |
| `GEMINI_API_KEY` | *(required)* | Gemini API key |
| `EMBEDDING_MODEL` | `gemini-embedding-001` | Embedding model |
| `GENERATION_MODEL` | `gemini-2.0-flash` | Generation model |
| `EMBEDDING_DIMENSIONS` | `768` | Vector dimensions |
| `CHUNK_SIZE` | `700` | Tokens per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap tokens |
| `UPLOAD_DIR` | `./uploads` | PDF storage path |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max upload size |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | `http://localhost:8000` | Backend URL |

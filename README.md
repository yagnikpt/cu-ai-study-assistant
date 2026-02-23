# AI Study Assistant

A RAG-based study tool that turns uploaded course material into an interactive
learning experience. Organize your materials into **Spaces**, upload PDFs, ask
questions grounded in your sources, generate structured summaries, and quiz
yourself — powered by Google Gemini, pgvector, and GitHub OAuth.

## Features

- **Spaces** — organize documents, Q&A, summaries, and quizzes into isolated
  study sessions; each user's data is fully private
- **GitHub OAuth** — sign in with your GitHub account; session managed via
  secure httpOnly JWT cookies
- **Document ingestion** — upload PDFs, automatically chunked with paragraph/heading
  awareness, embedded via Gemini, and indexed with HNSW for fast vector search
- **RAG Q&A** — ask questions and get cited answers grounded in your documents,
  streamed token-by-token via SSE for instant feedback
- **Summaries** — generate brief/standard/detailed summaries by topic or page range,
  with real-time SSE streaming
- **Quizzes** — auto-generate MCQ and short-answer quizzes, take them, get graded
  with per-question feedback and topic strength analysis

## Architecture

```
Browser (localhost:5173)
    |
    v
React SPA  ──(REST+SSE)──>  FastAPI Backend  ──>  PostgreSQL 17 + pgvector
(React Router 7,         (async, py3.13)      (HNSW vector index)
 shadcn/ui,                   |
 TanStack Query)              +──> GitHub OAuth (code exchange)
                              |
                              v
                         Google Gemini API
                         (embeddings + generation)
```

**Auth flow:** Browser → `/auth/github/login` → GitHub authorize → callback → upsert User → JWT cookie → redirect to `/spaces`

**Backend layers:** Routers (HTTP) -> Services (business logic) -> Models (ORM) -> Schemas (Pydantic)

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | FastAPI, Python 3.13, SQLAlchemy 2.0 (asyncpg), Alembic, pgvector, PyMuPDF, Google Gemini, PyJWT, httpx, uv |
| Frontend | React 19, React Router 7 (SPA mode), TypeScript, Vite 7, Tailwind CSS 4, shadcn/ui, TanStack Query 5, Bun |
| Database | PostgreSQL 17, pgvector (HNSW cosine similarity), Docker Compose |
| Auth | GitHub OAuth 2.0, JWT (httpOnly cookies, HS256) |

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
|       |-- config.py               # Pydantic Settings (DB, AI, OAuth, JWT)
|       |-- auth.py                 # JWT create/decode, get_current_user
|       |-- dependencies.py         # DBSession, CurrentUser
|       |-- models/document.py      # ORM models (User, Space, Document, Quiz, ...)
|       |-- schemas/                # Pydantic schemas (auth, space, document, qa, ...)
|       |-- routers/                # auth, spaces, documents, tags, qa, summaries, quizzes
|       +-- services/               # pdf_parser, chunker, embeddings,
|                                   # vector_search, qa, summary, quiz
|
+-- frontend/
    |-- package.json                # Bun deps
    |-- components.json             # shadcn/ui config
    +-- app/
        |-- root.tsx                # HTML shell + QueryClientProvider
        |-- routes.ts               # Route definitions (login, spaces, space/:id/...)
        |-- components/AuthProvider.tsx  # Auth context, redirect to /login
        |-- components/layout.tsx   # Sidebar (space name, nav, user avatar + logout)
        |-- components/ui/          # shadcn/ui components
        |-- lib/api.ts              # Typed fetch wrappers + SSE stream consumers
        |-- lib/types.ts            # TS interfaces (User, Space, Document, Quiz, ...)
        +-- routes/                 # login, spaces, documents, qa, summaries, quizzes,
                                    # quizzes.$quizId.take, quizzes.$quizId.results
```

## Getting Started

### Prerequisites

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/)
- Docker and Docker Compose
- [Google Gemini API key](https://aistudio.google.com/apikey)
- [GitHub OAuth App](https://github.com/settings/developers) (callback URL: `http://localhost:8000/auth/github/callback`)

### 1. Database

```bash
docker compose up -d
docker compose ps  # wait for "healthy"
```

### 2. Backend

```bash
cd backend
cp .env.example .env
# Edit .env — set GEMINI_API_KEY, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, JWT_SECRET
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

### Authentication

```
Browser -> GET /auth/github/login -> Redirect to GitHub
  -> User authorizes -> GitHub redirects to /auth/github/callback?code=XXX
  -> Backend exchanges code for access token
  -> Fetches GitHub profile (id, login, avatar_url, email)
  -> Upserts User record in DB
  -> Creates JWT, sets httpOnly "session" cookie
  -> Redirects to frontend /spaces
```

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
  -> pgvector cosine similarity search (top-k chunks, scoped to space documents)
  -> Build prompt (system: cite sources, use markdown, be educational)
  -> Gemini async streaming generation (temp=0.3)
  -> SSE: sources event -> token events (progressive) -> done event
  -> Frontend renders markdown progressively as tokens arrive
```

### Summaries

Two modes: **topic-based** (embed topic, search space docs) or **page-range**
(direct DB query). Detail levels: brief, standard, detailed. Both Q&A and
summaries stream via SSE — sources/metadata are sent first so the UI can
display them while tokens are still arriving.

### Quizzes

Generate MCQ/short-answer from document chunks via Gemini (strict JSON output).
Grade attempts (MCQ: exact match, short answer: substring). Track per-topic
accuracy, flag weak topics (<70%).

## API Reference

All endpoints under `/api/v1/`. Full Swagger UI at `/docs`.

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/github/login` | Redirect to GitHub OAuth |
| `GET` | `/auth/github/callback` | OAuth callback (exchanges code, sets cookie) |
| `GET` | `/api/v1/auth/me` | Get current authenticated user |
| `POST` | `/api/v1/auth/logout` | Clear session cookie |

### Spaces

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/spaces/` | Create space (scoped to current user) |
| `GET` | `/spaces/` | List user's spaces |
| `GET` | `/spaces/{id}` | Get space detail |
| `PATCH` | `/spaces/{id}` | Update space name/description |
| `DELETE` | `/spaces/{id}` | Delete space + all contents |

### Documents (scoped to space)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/spaces/{space_id}/documents/` | Upload PDF. Background ingestion. |
| `GET` | `/spaces/{space_id}/documents/` | List. Filters: course, subject, status, tag. |
| `GET` | `/spaces/{space_id}/documents/{id}` | Detail with chunk count and tags. |
| `PATCH` | `/spaces/{space_id}/documents/{id}` | Update course/subject. |
| `DELETE` | `/spaces/{space_id}/documents/{id}` | Delete document + chunks + file. |
| `POST` | `/spaces/{space_id}/documents/{id}/tags` | Add tags. |
| `GET` | `/spaces/{space_id}/documents/{id}/chunks` | View chunks (paginated). |

### Tags (global)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tags/` | Create tag. |
| `GET` | `/tags/` | List tags. |
| `DELETE` | `/tags/{id}` | Delete tag. |

### Q&A (scoped to space)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/spaces/{space_id}/qa/ask` | Ask question. Returns cited answer. |
| `POST` | `/spaces/{space_id}/qa/ask/stream` | Ask question (SSE stream). |
| `POST` | `/spaces/{space_id}/qa/search` | Semantic search only (no LLM). |

### Summaries (scoped to space)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/spaces/{space_id}/summaries/generate` | Generate summary. |
| `POST` | `/spaces/{space_id}/summaries/generate/stream` | Generate summary (SSE stream). |

### Quizzes (scoped to space)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/spaces/{space_id}/quizzes/generate` | Generate quiz. |
| `GET` | `/spaces/{space_id}/quizzes/` | List quizzes. |
| `GET` | `/spaces/{space_id}/quizzes/{id}` | Get quiz (answers hidden). |
| `POST` | `/spaces/{space_id}/quizzes/{id}/attempt` | Submit answers, get grading. |
| `GET` | `/spaces/{space_id}/quizzes/{id}/results` | Aggregated results + topic analysis. |

### SSE Streaming Protocol

The `/stream` endpoints use `text/event-stream` (Server-Sent Events). Each frame
has an `event` type and a `data` payload (JSON).

**Q&A stream** (`/qa/ask/stream`):

| Order | Event | Payload | Description |
|-------|-------|---------|-------------|
| 1 | `sources` | `SourceReference[]` | Retrieved sources (sent before generation starts) |
| 2..n | `token` | `string` | Text fragment from the LLM |
| last | `done` | `{ model }` | Generation complete |

**Summary stream** (`/summaries/generate/stream`):

| Order | Event | Payload | Description |
|-------|-------|---------|-------------|
| 1 | `meta` | `{ topic, sources }` | Topic + source list (sent before generation) |
| 2..n | `token` | `string` | Text fragment from the LLM |
| last | `done` | `{ model }` | Generation complete |

The frontend uses `fetch()` + `ReadableStream` to consume these events,
progressively rendering markdown as tokens arrive. Both pages support
aborting mid-stream via a Stop button.

## Database Schema

```
users  ----<  spaces  ----<  documents  ----<  document_chunks (embedding vec(768), HNSW index)
                 |               |
                 |               +---->  document_tags  >----  tags
                 |
                 +----<  quizzes  ----<  quiz_questions  ----<  quiz_attempts
```

Key: HNSW index on embeddings (`vector_cosine_ops`, m=16, ef_construction=64),
B-tree indexes on FKs/status/dates, auto-update triggers on `updated_at` columns.

## Configuration

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...localhost:5433/study_assistant` | DB connection |
| `GEMINI_API_KEY` | *(required)* | Gemini API key |
| `GITHUB_CLIENT_ID` | *(required)* | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | *(required)* | GitHub OAuth app client secret |
| `JWT_SECRET` | `change-me-in-production` | Secret for signing JWTs |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRY_HOURS` | `72` | Session duration |
| `FRONTEND_URL` | `http://localhost:5173` | Where to redirect after OAuth |
| `EMBEDDING_MODEL` | `text-embedding-004` | Embedding model |
| `GENERATION_MODEL` | `gemini-2.5-flash-lite` | Generation model |
| `EMBEDDING_DIMENSIONS` | `768` | Vector dimensions |
| `CHUNK_SIZE` | `700` | Tokens per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap tokens |
| `UPLOAD_DIR` | `./uploads` | PDF storage path |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max upload size |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | `http://localhost:8000` | Backend URL |

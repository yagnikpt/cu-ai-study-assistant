# AI Study Assistant

A RAG-based (Retrieval-Augmented Generation) backend API that turns uploaded course
material into an interactive study tool. Upload PDFs, ask questions grounded in your
sources, generate structured summaries, and quiz yourself -- all powered by
Google Gemini and semantic vector search.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Data Flow](#data-flow)
  - [Document Ingestion Pipeline](#1-document-ingestion-pipeline)
  - [RAG-Based Q&A](#2-rag-based-qa)
  - [Summary Generation](#3-summary-generation)
  - [Quiz Generation and Grading](#4-quiz-generation-and-grading)
- [Database Schema](#database-schema)
- [API Reference](#api-reference)
- [Getting Started](#getting-started)
- [Configuration](#configuration)

---

## Architecture Overview

```
                         +------------------+
                         |   FastAPI App     |
                         |   (async, py3.13)|
                         +--------+---------+
                                  |
              +-------------------+-------------------+
              |                   |                   |
     +--------v--------+ +-------v--------+ +--------v--------+
     |    Routers       | |   Services     | |   Schemas       |
     | (documents, qa,  | | (pdf_parser,   | | (pydantic       |
     |  summaries,      | |  chunker,      | |  request/       |
     |  quizzes, tags)  | |  embeddings,   | |  response       |
     +---------+--------+ |  vector_search,| |  models)        |
               |          |  qa_service,   | +-----------------+
               |          |  summary_svc,  |
               |          |  quiz_service) |
               |          +-------+--------+
               |                  |
      +--------v------------------v--------+
      |        PostgreSQL 17 + pgvector     |
      |   (documents, chunks, embeddings,   |
      |    quizzes, tags -- HNSW index)     |
      +-------------------+----------------+
                          |
              +-----------v-----------+
              |    Google Gemini API   |
              |  - gemini-embedding-  |
              |    001 (embeddings)   |
              |  - gemini-flash       |
              |    (generation)       |
              +----------------------+
```

The API follows a clean layered architecture:

- **Routers** handle HTTP concerns (validation, status codes, response shaping)
- **Services** contain all business logic (parsing, chunking, AI calls, search)
- **Models** define the SQLAlchemy ORM mappings
- **Schemas** define Pydantic request/response contracts

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Web Framework | FastAPI (async) | Native async support, auto-generated OpenAPI docs |
| Language | Python 3.13 | Latest stable, modern type hints |
| Database | PostgreSQL 17 | Robust relational storage |
| Vector Search | pgvector (HNSW) | Vector similarity search inside Postgres -- no separate vector DB |
| ORM | SQLAlchemy 2.0 (asyncpg) | Async support, mature ecosystem |
| Migrations | Alembic (raw SQL) | Full control over schema changes |
| LLM Provider | Google Gemini | Embedding + generation from one provider |
| Embedding Model | `gemini-embedding-001` | 768-dim output (via dimensionality reduction) |
| Generation Model | Configurable (e.g. `gemini-2.0-flash`) | Fast, capable generation |
| PDF Parsing | PyMuPDF | Block-level text extraction with font metadata |
| Package Manager | uv | Fast, reliable Python dependency management |
| Dev Database | Docker Compose | One-command Postgres + pgvector setup |

---

## Project Structure

```
cu_study_assistant/
|-- main.py                    # Uvicorn entry point
|-- pyproject.toml             # Project config + dependencies
|-- docker-compose.yml         # PostgreSQL + pgvector service
|-- alembic.ini                # Alembic config
|-- .env.example               # Environment variable template
|
|-- alembic/
|   |-- env.py                 # Migration runner (reads app config)
|   +-- versions/
|       +-- 001_initial_schema.py  # Full schema in raw SQL
|
+-- app/
    |-- main.py                # FastAPI app, lifespan, router registration
    |-- config.py              # Pydantic Settings (loads .env)
    |-- database.py            # Async engine + session factory
    |-- dependencies.py        # DBSession type alias for DI
    |
    |-- models/
    |   +-- document.py        # All ORM models (Document, Chunk, Tag, Quiz, etc.)
    |
    |-- schemas/
    |   |-- document.py        # Document/Tag request & response schemas
    |   |-- qa.py              # Q&A schemas
    |   |-- summary.py         # Summary schemas
    |   +-- quiz.py            # Quiz schemas
    |
    |-- routers/
    |   |-- documents.py       # Upload, CRUD, tagging, chunk viewing
    |   |-- tags.py            # Tag CRUD
    |   |-- qa.py              # Ask questions, semantic search
    |   |-- summaries.py       # Generate summaries
    |   +-- quizzes.py         # Generate quizzes, submit attempts, view results
    |
    +-- services/
        |-- pdf_parser.py      # PyMuPDF text extraction with heading detection
        |-- chunker.py         # Semantic chunking (paragraph-aware, heading-aware)
        |-- embeddings.py      # Gemini embedding generation (batched)
        |-- vector_search.py   # pgvector cosine similarity search
        |-- qa_service.py      # RAG pipeline (embed -> search -> prompt -> generate)
        |-- summary_service.py # Topic/page-range summary generation
        +-- quiz_service.py    # Quiz generation, grading, progress tracking
```

---

## Data Flow

### 1. Document Ingestion Pipeline

When a PDF is uploaded via `POST /api/v1/documents/`, the system processes it
through a background pipeline:

```
Upload PDF
    |
    v
[Save to disk]  -->  Create DB record (status: "processing")
    |
    v  (background task)
[PDF Parser]
    |  PyMuPDF extracts text blocks per page
    |  Detects headings via font size heuristic (>14pt)
    |  Preserves document structure (blocks -> lines -> spans)
    v
[Semantic Chunker]
    |  Splits text at paragraph boundaries (never mid-paragraph)
    |  Respects heading boundaries (new section = new chunk)
    |  Target size: ~700 tokens per chunk with 100-token overlap
    |  Tracks page numbers, section titles, paragraph count
    v
[Embedding Generator]
    |  Sends chunks to Gemini API in batches of 100
    |  gemini-embedding-001 with output_dimensionality=768
    |  Returns 768-dimensional float vectors
    v
[Store in PostgreSQL]
    |  Inserts DocumentChunk rows with embedding vectors
    |  HNSW index auto-indexes new vectors
    |  Updates document status to "ready"
    v
Document is now searchable
```

**Key design decisions:**

- **Paragraph-aware chunking** instead of naive sliding window -- chunks never
  break mid-paragraph, producing more coherent retrieval units.
- **Heading-aware splitting** -- when a heading is encountered, the current chunk
  is flushed and a new one starts, preserving topical boundaries.
- **Overlap** -- the last ~100 tokens of each chunk carry over to the next,
  ensuring context isn't lost at chunk boundaries.
- **Background processing** -- the upload endpoint returns immediately with
  `status: "processing"`. Clients poll the document endpoint to check when
  ingestion completes.

### 2. RAG-Based Q&A

When a question is asked via `POST /api/v1/qa/ask`:

```
User Question: "What is supervised learning?"
    |
    v
[Embed Question]
    |  Same Gemini embedding model used for chunks
    |  Produces a 768-dim query vector
    v
[Vector Search]  (pgvector cosine similarity)
    |  HNSW index finds top-k nearest chunks
    |  Filters: document status = "ready", optional document_id filter
    |  Returns chunks ranked by similarity score
    v
[Build Prompt]
    |  System prompt instructs: answer ONLY from sources, cite with
    |  [Source: filename, p.X], use markdown, be educational
    |  Context section formats each chunk with source metadata
    v
[Gemini Generation]
    |  temperature=0.3 (low creativity, high fidelity)
    |  max_output_tokens=2048
    v
[Response]
    |  Structured answer with inline citations
    |  Source reference list (chunk_id, doc name, pages, relevance score)
    +-- Example: "In supervised learning, the algorithm learns from
        labeled training data [Source: ml_intro.pdf, p.1]..."
```

**Source attribution** is enforced at the prompt level -- the LLM is instructed
to only use provided context and to cite every claim. The response includes
machine-readable source references alongside the answer text.

There is also a `POST /api/v1/qa/search` endpoint that performs just the vector
search step without LLM generation, useful for exploring what the system "knows"
about a topic.

### 3. Summary Generation

`POST /api/v1/summaries/generate` supports two modes:

```
Mode A: Topic-based                    Mode B: Page-range
"topic": "neural networks"            "document_id": "...",
                                       "page_start": 5, "page_end": 10
    |                                      |
    v                                      v
[Embed topic, search all docs]        [Direct DB query for chunks
 top_k=10 chunks]                      within page range]
    |                                      |
    +---------------+----------------------+
                    |
                    v
          [Build summary prompt]
           detail_level: brief | standard | detailed
           - brief: 2-3 paragraph overview
           - standard: section-by-section breakdown
           - detailed: in-depth with examples
                    |
                    v
          [Gemini Generation]
           temperature=0.4, max_tokens=4096
                    |
                    v
          Structured markdown summary
          with [Source: doc, p.X] citations
```

### 4. Quiz Generation and Grading

#### Generating a Quiz

`POST /api/v1/quizzes/generate`:

```
Input: document_id and/or topic,
       question_count (1-20),
       question_types: ["mcq", "short_answer"]
    |
    v
[Retrieve relevant chunks]
    |  Topic search or full document chunks (limit 15)
    v
[Generate quiz via Gemini]
    |  System prompt enforces strict JSON output schema:
    |  {
    |    "questions": [{
    |      "type": "mcq",
    |      "question": "...",
    |      "options": [{"label":"A","text":"...","is_correct":true}, ...],
    |      "correct_answer": "A",
    |      "explanation": "...",
    |      "source_pages": "p.3"
    |    }]
    |  }
    |  temperature=0.5 for variety
    v
[Parse JSON, store in DB]
    |  Creates Quiz + QuizQuestion records
    |  Stores source_chunk_ids for traceability
    v
Return quiz (questions WITHOUT answers)
```

#### Submitting an Attempt

`POST /api/v1/quizzes/{id}/attempt`:

```
Submit: [{"question_id": "...", "answer": "B"}, ...]
    |
    v
[Grade each answer]
    |  MCQ: exact label match (case-insensitive)
    |  Short answer: substring containment check
    v
[Store QuizAttempt records]
    |  Records user_answer, is_correct, feedback per question
    v
Return: score_percentage, correct_count,
        per-question feedback with explanations
```

#### Viewing Results

`GET /api/v1/quizzes/{id}/results` aggregates all attempts into:
- Overall best score and attempt count
- Per-topic accuracy breakdown
- Topics flagged for reinforcement (accuracy < 70%)

---

## Database Schema

```
+-------------------+       +--------------------+       +----------+
|    documents      |       |  document_chunks   |       |   tags   |
+-------------------+       +--------------------+       +----------+
| id (UUID, PK)     |<---+  | id (UUID, PK)      |       | id (PK)  |
| filename          |    |  | document_id (FK) ---+       | name     |
| original_filename |    |  | content (TEXT)      |       | color    |
| file_path         |    |  | chunk_index (INT)   |       +----+-----+
| file_size_bytes   |    |  | page_start          |            |
| page_count        |    |  | page_end            |     +------+-------+
| course_name       |    |  | section_title       |     | document_tags |
| subject           |    |  | embedding vec(768)  |     | (M2M junction)|
| status (enum)     |    |  | token_count         |     | document_id   |
| error_message     |    |  | metadata (JSONB)    |     | tag_id        |
| created_at        |    |  | created_at          |     +--------------+
| updated_at        |    |  +--------------------+
+-------------------+    |
         |               |
         |    +----------+---------+
         |    |     quizzes        |
         +--->| id (UUID, PK)      |
              | title              |
              | document_id (FK)   |
              | topic              |
              | question_count     |
              | created_at         |
              +--------+-----------+
                       |
              +--------v-----------+       +------------------+
              |  quiz_questions    |       |  quiz_attempts   |
              | id (UUID, PK)      |<------| id (UUID, PK)    |
              | quiz_id (FK)       |       | quiz_id (FK)     |
              | question_type      |       | question_id (FK) |
              | question_text      |       | user_answer      |
              | options (JSONB)    |       | is_correct       |
              | correct_answer     |       | feedback         |
              | explanation        |       | attempted_at     |
              | source_chunk_ids   |       +------------------+
              | source_pages       |
              +--------------------+
```

**Notable indexes:**

- `idx_chunks_embedding_hnsw` -- HNSW index on the embedding column using
  `vector_cosine_ops` (m=16, ef_construction=64). This is what makes vector
  search fast.
- Standard B-tree indexes on foreign keys, status, course_name, and created_at
  for efficient filtering and sorting.
- A database trigger auto-updates `documents.updated_at` on any row change.

---

## API Reference

All endpoints are under `/api/v1/` except the health checks. Full interactive
docs are available at `/docs` (Swagger UI) when the server is running.

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | API info (name, version, status) |
| `GET` | `/health` | Database connectivity + Gemini configuration check |

### Documents

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/documents/` | Upload a PDF (multipart form, `file` field). Optional query params: `course_name`, `subject`. Returns immediately; ingestion runs in background. |
| `GET` | `/api/v1/documents/` | List documents. Filters: `course_name`, `subject`, `status`, `tag_id`. Pagination: `offset`, `limit`. |
| `GET` | `/api/v1/documents/{id}` | Get document details including chunk count and tags. |
| `PATCH` | `/api/v1/documents/{id}` | Update `course_name` or `subject`. |
| `DELETE` | `/api/v1/documents/{id}` | Delete document, its chunks, embeddings, and file from disk. |
| `POST` | `/api/v1/documents/{id}/tags` | Add tags to a document. Body: `{"tag_ids": ["..."]}` |
| `DELETE` | `/api/v1/documents/{id}/tags/{tag_id}` | Remove a tag from a document. |
| `GET` | `/api/v1/documents/{id}/chunks` | View chunks (paginated). Useful for inspecting what was extracted. |

### Tags

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/tags/` | Create a tag. Body: `{"name": "...", "color": "#FF5733"}` |
| `GET` | `/api/v1/tags/` | List all tags. |
| `DELETE` | `/api/v1/tags/{id}` | Delete a tag. |

### Q&A

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/qa/ask` | Ask a question. Body: `{"question": "...", "document_ids": [...], "top_k": 5}`. Returns answer with source citations. |
| `POST` | `/api/v1/qa/search` | Semantic search only. Body: `{"query": "...", "top_k": 10}`. Returns ranked chunks without LLM generation. |

### Summaries

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/summaries/generate` | Generate a summary. Body: `{"topic": "...", "document_id": "...", "detail_level": "standard"}`. At least one of `topic` or `document_id` required. |

### Quizzes

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/quizzes/generate` | Generate a quiz. Body: `{"document_id": "...", "num_questions": 5, "question_types": ["mcq", "short_answer"]}` |
| `GET` | `/api/v1/quizzes/` | List quizzes. Optional filter: `document_id`. |
| `GET` | `/api/v1/quizzes/{id}` | Get quiz with questions (answers hidden -- for taking the quiz). |
| `POST` | `/api/v1/quizzes/{id}/attempt` | Submit answers. Body: `{"answers": [{"question_id": "...", "answer": "B"}]}`. Returns grading + feedback. |
| `GET` | `/api/v1/quizzes/{id}/results` | Aggregated results: best score, attempt count, topic strength analysis. |

---

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker and Docker Compose
- A Google Gemini API key ([get one here](https://aistudio.google.com/apikey))

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd cu_study_assistant
uv sync
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and set your Gemini API key:

```
GEMINI_API_KEY=your-actual-api-key
```

### 3. Start the database

```bash
docker compose up -d
```

This starts PostgreSQL 17 with the pgvector extension on port **5433** (to avoid
conflicts with any local Postgres on 5432).

Wait for the health check to pass:

```bash
docker compose ps   # STATUS should show "healthy"
```

### 4. Run database migrations

```bash
uv run alembic upgrade head
```

This creates all tables, indexes (including the HNSW vector index), enums, and
triggers.

### 5. Start the server

```bash
uv run python main.py
```

The API will be available at `http://localhost:8000`. Interactive docs are at
`http://localhost:8000/docs`.

### 6. Verify everything works

```bash
# Health check
curl http://localhost:8000/health

# Upload a PDF
curl -X POST http://localhost:8000/api/v1/documents/ \
  -F "file=@your_notes.pdf"

# Check ingestion status (use the id from the upload response)
curl http://localhost:8000/api/v1/documents/<document-id>

# Ask a question (once status is "ready")
curl -X POST http://localhost:8000/api/v1/qa/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the main topics covered?"}'
```

---

## Configuration

All configuration is managed through environment variables (loaded from `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://study_assistant:study_assistant@localhost:5433/study_assistant` | Async database connection string |
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `EMBEDDING_MODEL` | `text-embedding-004` | Gemini embedding model name |
| `GENERATION_MODEL` | `gemini-2.0-flash` | Gemini generation model name |
| `EMBEDDING_DIMENSIONS` | `768` | Output dimensionality for embeddings (max 2000 for HNSW) |
| `CHUNK_SIZE` | `700` | Target tokens per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap tokens between consecutive chunks |
| `UPLOAD_DIR` | `./uploads` | Directory for storing uploaded PDFs |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum upload file size in megabytes |

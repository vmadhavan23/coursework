# Table Tennis Match Stats

An open-source, locally-runnable app for scoring a table tennis match point-by-point and generating
match statistics afterward — final scores, serve win %, longest streaks, tag counts (aces, unforced
errors, winners), and closest/most one-sided games. Built for recreational players and sideline
scorers/coaches; no cloud account, network dependency, or special hardware required.

This is an MVP/demo-scope project (see [`requirements.md`](requirements.md)): no auth, no multi-user
support, no production hardening.

Two optional add-ons sit outside that MVP scope, each independently configurable and each disabled
by default:

- **AI video match report** — paste a video URL (YouTube supported) and get a best-effort, AI-generated
  read of the match (summary, estimated score, notable moments, confidence, caveats). Standalone —
  never touches match/point data or the scoring engine.
- **RAG indexing** — on match completion, and on a successful video analysis, a plain-text summary is
  (best-effort) written to a RAG knowledge index for future reference.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python + FastAPI, SQLite (single file, stdlib `sqlite3`) |
| Frontend | React SPA (Vite) |
| AI video analysis | Google Gemini (`google-genai`) |
| RAG index | DataStax Astra DB (`astrapy`) |

## Project layout

```
backend/            FastAPI app, scoring engine, SQLite schema, tests
  app/
    main.py          Routes
    scoring.py        Pure scoring/serve-rotation functions
    repository.py      DB reads/writes
    stats.py           Match summary/statistics
    video_analysis.py   Gemini-backed video analysis (optional add-on)
    rag_integration.py  Astra DB ingestion (optional add-on)
  tests/            pytest suite
frontend/           React SPA (Vite)
requirements.md     Numbered functional requirements (REQ-001...)
design.md           Data model, architecture, REQ-to-endpoint traceability
openapi.yaml        OpenAPI 3.1 spec (every endpoint tagged with its REQ-IDs)
todo.md             Implementation task list with test evidence
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- (Optional) A Gemini API key, for AI video analysis
- (Optional) An Astra DB database (API endpoint + application token), for RAG indexing

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # or: uv pip install -r requirements.txt

cp .env.example .env
# Edit .env: DATABASE_PATH is set by default; ASTRA_DB_* and GEMINI_API_KEY are optional
```

### Frontend

```bash
cd frontend
npm install
```

## Running

```bash
# Terminal 1 — backend (http://127.0.0.1:8000, docs at /docs)
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — frontend (http://127.0.0.1:5173)
cd frontend
npm run dev
```

The Vite dev server proxies `/api` requests to the backend, so no CORS configuration is needed.
Open `http://127.0.0.1:5173` and start a new match, or go to "Analyze Video" to try the AI report
feature (requires `GEMINI_API_KEY`).

## Testing

```bash
cd backend
pytest
```

Covers the scoring engine, the full HTTP API (every REQ's acceptance criteria), the OpenAPI contract
(spec vs. the app's actual routes/operationIds), and both optional add-ons with fake clients (no real
network calls in the test suite).

## Configuration reference

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_PATH` | No (defaults to `./tabletennis.db`) | SQLite file location |
| `ASTRA_DB_API_ENDPOINT`, `ASTRA_DB_APPLICATION_TOKEN` | No | Enables RAG indexing on match completion / video analysis. Leave unset to disable (ingestion is skipped silently, never errors) |
| `GEMINI_API_KEY` | No | Enables `POST /video-analysis`. Leave unset to disable (endpoint returns `503`) |

## Documentation

- [`requirements.md`](requirements.md) — functional requirements (REQ-001–029) with acceptance criteria
- [`design.md`](design.md) — data model, architecture, REQ-to-endpoint traceability
- [`openapi.yaml`](openapi.yaml) — full API spec
- [`todo.md`](todo.md) — implementation history with test evidence for every task

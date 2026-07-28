# Implementation TODO

Derived from `requirements.md`, `design.md`, and `openapi.yaml`. Each task is implemented, then tested,
then checked off below only once its tests pass. Credentials/config (`OPENRAG_URL`, `OPENRAG_API_KEY`,
`DATABASE_PATH`) are read from `backend/.env` (never hardcoded).

## Backend (Python + FastAPI + SQLite)

- [x] T01 — Scaffold backend project: package layout, dependencies, `.env`/`.env.example`, config loading — `pytest tests/test_database.py::test_settings_load_from_env test_settings_openrag_disabled_without_api_key` pass
- [x] T02 — SQLite schema & connection layer (`players`, `matches`, `games`, `points`, FK enforcement) — `pytest tests/test_database.py` 6/6 pass (round-trip, FK pragma, unique constraint, cascade delete)
- [x] T03 — Scoring engine (pure functions): deuce-aware game win, match win, serve rotation — `pytest tests/test_scoring.py` 20/20 pass
- [x] T04 — `POST /matches` — match setup (REQ-001, REQ-002, REQ-003, REQ-004) — covered by `tests/test_api.py` (5 tests)
- [x] T05 — `GET /matches/{id}` + `POST /matches/{id}/points` — live scoring (REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-011, REQ-012, REQ-019) — covered by `tests/test_api.py` (8 tests incl. deuce)
- [x] T06 — `DELETE /matches/{id}/points/last` — undo (REQ-010) — covered by `tests/test_api.py` (5 tests incl. cross-game-boundary reopen)
- [x] T07 — `POST /matches/{id}/abandon`, `POST /matches/{id}/reset` — match control (REQ-023, REQ-024) — covered by `tests/test_api.py` (4 tests)
- [x] T08 — Statistics engine + `GET /matches/{id}/summary` (REQ-013, REQ-014, REQ-015, REQ-016, REQ-017, REQ-018, REQ-021) — covered by `tests/test_api.py` (3 tests, expected stats cross-checked against the scoring engine)
- [x] T09 — `GET /matches` + `DELETE /matches/{id}` — history (REQ-020, REQ-022) — covered by `tests/test_api.py` (3 tests)

`pytest` full suite: 58/58 passing (`tests/test_database.py`, `tests/test_scoring.py`, `tests/test_api.py`).
- [x] T10 — OpenRAG ingestion wiring on match completion — best-effort, `.env`-configured (REQ-019 side effect) — `pytest tests/test_openrag_integration.py` 6/6 pass (skip w/o key, success, swallowed failure, full API flow both ways)
- [x] T11 — Cross-check FastAPI's generated OpenAPI paths/operationIds against the committed `openapi.yaml` — found & fixed 2 real gaps: path param was `match_id` vs spec's `matchId`, and default-generated `operationId`s didn't match; `pytest tests/test_openapi_contract.py` 4/4 pass

**Backend `pytest` full suite: 68/68 passing.**

## Frontend (React SPA)

- [x] T12 — Scaffold React (Vite) app + API client module — `npm install` (65 pkgs) + `npm run build` succeed cleanly
- [x] T13 — New Match view (Flow 1) — implemented (`src/pages/NewMatch.jsx`), verified in T17
- [x] T14 — Live Scoring view (Flow 2 & 5: score, tag, undo, abandon, reset, serve indicator) — implemented (`src/pages/LiveScoring.jsx`), verified in T17
- [x] T15 — Match Summary view (Flow 3 completion & Flow 4 reopen) — implemented (`src/pages/MatchSummary.jsx`), verified in T17
- [x] T16 — History view (Flow 4: list + delete) — implemented (`src/pages/History.jsx`), verified in T17
- [x] T17 — End-to-end smoke test of a full match through the running app (backend + frontend together) — real `uvicorn` + `vite` dev servers, driven with Playwright/Chromium through all 5 user flows (new match, live scoring incl. serve rotation/tag/undo, match completion, summary, history reopen + delete, abandon, reset); all assertions passed, servers stopped cleanly after

## Notes
- Backend tests: `pytest` (unit tests for the scoring/stats engines, API tests via FastAPI's `TestClient`).
- Frontend: manual/browser smoke testing via the pre-installed Chromium, since this MVP has no frontend
  test framework configured (kept out of scope to match "no production-level" tooling).

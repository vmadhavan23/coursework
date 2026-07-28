# Table Tennis Match Stats App — Design

Companion to `requirements.md`. Covers the data model, the (minimal) OpenRAG integration and its
knowledge filters, the REQ-to-endpoint traceability, and the technical requirements for the frontend
and backend. Stack decisions below were confirmed with the project owner rather than assumed:

| Decision | Choice |
|---|---|
| Backend | Python + FastAPI |
| Frontend | React SPA |
| Local structured-data storage | SQLite (single file) |
| OpenRAG's role | Minimal wiring only — ingest completed-match summaries for future use; no chat/search feature built yet |

## Architecture Overview

```
React SPA  ──REST──▶  FastAPI backend  ──reads/writes──▶  SQLite (match/game/point data)
                              │
                              └──best-effort, async──▶  OpenRAG (openrag-sdk, Python)
                                                          document ingestion only
```

- The SPA never talks to OpenRAG directly — all traffic goes through the backend's own REST API
  (`openapi.yaml`), keeping any future `OPENRAG_API_KEY` server-side only.
- SQLite is the source of truth for everything the API serves (scores, history, stats). OpenRAG is a
  side-channel: a copy of each completed match's summary is ingested as a document so a later feature
  (semantic search or chat over match history) can be added without re-processing old matches. If OpenRAG
  is unreachable, match completion and saving to history (REQ-019) must still succeed — ingestion failures
  are logged and swallowed, never surfaced to the user or allowed to block the request.

## Data Model (SQLite)

### `players`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `display_name` | TEXT, unique, not null | Get-or-create by exact name match when a match is created (REQ-001); no separate player-management UI/endpoint exists — this table exists purely so match history (REQ-020) can group/display names consistently. |
| `created_at` | TEXT (ISO 8601) | |

### `matches`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `player_one_id`, `player_two_id` | INTEGER FK → `players.id` | Must differ (REQ-001). |
| `points_to_win` | INTEGER, not null | e.g. 11 or 21 (REQ-002). |
| `games_to_win` | INTEGER, not null | Derived from best-of-N at creation time (best-of-3 → 2, best-of-5 → 3) (REQ-003). |
| `status` | TEXT enum: `in_progress`, `completed`, `abandoned` | REQ-009, REQ-023. |
| `serving_player_id` | INTEGER FK → `players.id`, nullable | Recomputed on every point (REQ-012). |
| `winner_player_id` | INTEGER FK → `players.id`, nullable | Set only when `status = completed`. |
| `created_at`, `completed_at` | TEXT (ISO 8601), `completed_at` nullable | |

### `games`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `match_id` | INTEGER FK → `matches.id` | |
| `game_number` | INTEGER, not null | 1-indexed, unique per match. |
| `player_one_score`, `player_two_score` | INTEGER, default 0 | Reset to 0–0 at the start of each game (REQ-008). |
| `winner_player_id` | INTEGER FK → `players.id`, nullable | Set once the deuce-aware win condition is met (REQ-007). |
| `completed_at` | TEXT (ISO 8601), nullable | |

### `points`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `game_id` | INTEGER FK → `games.id` | |
| `sequence_number` | INTEGER, not null | 1-indexed within the game; used to identify "the last point" for undo (REQ-010). |
| `winner_player_id` | INTEGER FK → `players.id`, not null | |
| `served_by_player_id` | INTEGER FK → `players.id`, not null | Computed from the serve-rotation rule at the time the point was recorded (REQ-012), not re-derived later, so undo can restore it exactly. |
| `tag` | TEXT enum: `ace`, `unforced_error`, `winner`, nullable | Optional per point (REQ-011). |
| `created_at` | TEXT (ISO 8601) | |

### Business rules encoded in the model (not just the API layer)
- **Undo (REQ-010)** only ever removes the single highest-`sequence_number` point in the current game. If
  that point had caused the game (and possibly the match) to complete, undo must also reopen the game
  (clear `games.winner_player_id`/`completed_at`) and, if applicable, reopen the match
  (`matches.status` back to `in_progress`, clear `winner_player_id`/`completed_at`). Undo never reaches back
  into an already-fully-closed previous game.
- **Serve rotation (REQ-012)** is a pure function of `sequence_number` and `points_to_win`: serve changes
  every 2 points normally, every 1 point once both scores are ≥ `points_to_win − 1` (deuce). Storing
  `served_by_player_id` per point (rather than recomputing from current state) is what makes undo exact.
- **Abandon (REQ-023)** deletes the match row (and cascades to its games/points) rather than marking it
  `abandoned` and keeping it queryable — REQ-023's acceptance criterion is that no record appears anywhere
  in history, so a soft status alone would not satisfy it.

## OpenRAG Integration (Minimal)

Per the confirmed scope, OpenRAG is wired up only far enough to make a later stats-chat/search feature
possible — no new user-facing behavior ships yet, and there is no OpenRAG-backed endpoint in
`openapi.yaml`. Everything below happens as a side effect of match completion (REQ-019), following the
`openrag_sdk` skill's integration and error-handling patterns.

### What gets ingested
When a match transitions to `status = completed`, the backend builds a plain-text summary (players, final
score per game, match result, tag totals — the same data returned by `GET /matches/{id}/summary`) and
ingests it as a document:

```python
from openrag_sdk import OpenRAGClient, OpenRAGError

async def ingest_match_summary(match_id: int, summary_text: str) -> None:
    try:
        async with OpenRAGClient() as client:  # reads OPENRAG_URL / OPENRAG_API_KEY from env
            await client.documents.ingest(
                file=io.BytesIO(summary_text.encode("utf-8")),
                filename=f"match-{match_id}.txt",
            )
    except OpenRAGError:
        log.warning("OpenRAG ingestion failed for match %s; continuing without it", match_id)
```

- Filename convention: `match-{match_id}.txt` — deterministic and unique, so a future feature can look up
  or re-ingest a specific match's document without a separate ID-mapping table.
- This call is fire-and-forget relative to the HTTP response: the API request that completes the match
  (`POST /matches/{id}/points`) returns as soon as SQLite is updated; ingestion runs after and its failure
  is only logged (per the skill's "Fallback handling" guidance), never surfaced as an API error.
- `OPENRAG_URL` and (if the target OpenRAG instance has auth enabled) `OPENRAG_API_KEY` are read from
  environment variables, matching the SDK's auto-discovery behavior — no OpenRAG config is hardcoded or
  exposed to the frontend.

### Knowledge filters needed

Two filter shapes are specified now so a later feature can adopt them without redesigning the ingestion
side. Consistent with the SDK's `SearchFilters`/`knowledge_filters` API, both scope by `data_sources`
(the filenames ingested above) rather than by custom metadata fields, since OpenRAG filters don't support
arbitrary key/value metadata:

1. **Per-match filter** — scopes to exactly one match's document.
   ```json
   {
     "name": "Match #{match_id}",
     "description": "Scope to a single match's summary",
     "queryData": { "filters": { "data_sources": ["match-{match_id}.txt"] } }
   }
   ```
2. **Per-player filter** — scopes to every match a given player has appeared in. The backend already
   knows, from the `matches`/`players` tables, every `match-{id}.txt` filename involving a given
   `player_id`, so this filter's `data_sources` list can be (re)computed at creation/update time.
   ```json
   {
     "name": "Player: {display_name}",
     "description": "Scope to every match this player has played",
     "queryData": { "filters": { "data_sources": ["match-12.txt", "match-19.txt", "..."] } }
   }
   ```

**Not built in this iteration**: actually calling `client.knowledge_filters.create(...)` /
`.update(...)`, and any endpoint that calls `client.chat.create()` or `client.search.query()` with these
filters. That is deliberately out of scope per the "minimal wiring" decision — the filter shapes above are
the contract a future iteration would implement against.

## Requirements Traceability

Every endpoint in `openapi.yaml` maps to at least one REQ from `requirements.md`, and every functional
requirement maps to at least one endpoint (the same table appears as `x-req-ids` on each operation in the
OpenAPI spec):

| REQ | Endpoint | Notes |
|---|---|---|
| REQ-001 | `POST /matches` | Two distinct, non-empty player names required. |
| REQ-002 | `POST /matches` | `points_to_win` in request body. |
| REQ-003 | `POST /matches` | `best_of` in request body, converted to `games_to_win`. |
| REQ-004 | `POST /matches` | Invalid/incomplete setup → `422`. |
| REQ-005 | `POST /matches/{id}/points` | Records one point's winner. |
| REQ-006 | `GET /matches/{id}` | Current running score, polled/refetched by the client. |
| REQ-007 | `POST /matches/{id}/points` | Deuce-aware game-win detection. |
| REQ-008 | `POST /matches/{id}/points` | Auto-starts next game, preserves games-won tally. |
| REQ-009 | `POST /matches/{id}/points` | Match-win detection from `games_to_win`. |
| REQ-010 | `DELETE /matches/{id}/points/last` | Undoes only the most recent point. |
| REQ-011 | `POST /matches/{id}/points` | Optional `tag` field. |
| REQ-012 | `GET /matches/{id}`, `POST /matches/{id}/points` | Serve indicator in both responses. |
| REQ-013 | `GET /matches/{id}/summary` | Per-game score list + games-won tally. |
| REQ-014 | `GET /matches/{id}/summary` | Total points won per player. |
| REQ-015 | `GET /matches/{id}/summary` | Serve win % per player (when available). |
| REQ-016 | `GET /matches/{id}/summary` | Longest win streak per player. |
| REQ-017 | `GET /matches/{id}/summary` | Tag totals per player. |
| REQ-018 | `GET /matches/{id}/summary` | Closest / most one-sided game. |
| REQ-019 | `POST /matches/{id}/points` | Side effect: persists the completed match; triggers OpenRAG ingestion. |
| REQ-020 | `GET /matches` | Reverse-chronological history list. |
| REQ-021 | `GET /matches/{id}/summary` | Reopen a past match's full stats. |
| REQ-022 | `DELETE /matches/{id}` | Removes a match from history. |
| REQ-023 | `POST /matches/{id}/abandon` | Discards an in-progress match entirely. |
| REQ-024 | `POST /matches/{id}/reset` | Restarts the same match at 0–0. |

## Technical Requirements — Backend

- **Runtime**: Python 3.11+ (any interpreter able to run FastAPI and `openrag-sdk`'s async client); this
  is independent of the Python 3.13 requirement noted in the separate `openrag_install` skill, which
  governs the standalone OpenRAG service, not this app.
- **Framework**: FastAPI + Uvicorn (ASGI), chosen so OpenRAG SDK calls (async-only) can be awaited natively
  inside request handlers without a sync/async bridge.
- **Validation**: Pydantic models mirroring the `openapi.yaml` schemas; request validation enforces
  REQ-004 (distinct non-empty names, `points_to_win` ∈ {11, 21}, `best_of` ∈ {1, 3, 5}).
- **Scoring engine**: the deuce/game-win/match-win/serve-rotation rules (REQ-007/008/009/012) live in a
  module with no HTTP or persistence dependencies, so they can be unit-tested against point sequences
  directly.
- **Persistence**: a single SQLite file (path from a `DATABASE_PATH` env var, default e.g.
  `./tabletennis.db`), schema as above, foreign keys enforced (`PRAGMA foreign_keys = ON`).
- **OpenRAG client**: one `OpenRAGClient` per process (or per-request, since the SDK is a lightweight async
  context manager), configured from `OPENRAG_URL` / `OPENRAG_API_KEY` env vars; all calls wrapped per the
  `openrag_sdk` skill's error-handling guidance so `OpenRAGError` never propagates to the HTTP layer.
- **No authentication/authorization** anywhere in this API — matches the MVP's explicit no-security-concerns
  scope (single local user, no network exposure by default).
- **Binding**: local dev server bound to `127.0.0.1` only, not `0.0.0.0` — this is a "locally-runnable app"
  default, not a hardening measure.

## Technical Requirements — Frontend

- **Framework**: React SPA (Vite dev server), no meta-framework/SSR needed for a local MVP.
- **Routing/views** (one per user flow in `requirements.md`):
  - *Home / New Match* (Flow 1) → `POST /matches`
  - *Live Scoring* (Flow 2 and 5) → `GET /matches/{id}` (poll or refetch after each action),
    `POST /matches/{id}/points`, `DELETE /matches/{id}/points/last`,
    `POST /matches/{id}/abandon`, `POST /matches/{id}/reset`
  - *Match Summary* (Flow 3 completion, and reused for Flow 4 detail view) → `GET /matches/{id}/summary`
  - *History List* (Flow 4) → `GET /matches`, `DELETE /matches/{id}`
- **State management**: local component state / React Context is sufficient — no Redux/global store needed
  at this scope.
- **Networking**: `fetch` against the backend's own REST API only; the frontend never calls OpenRAG or
  holds an `OPENRAG_API_KEY` directly, keeping the (currently nonexistent, future) key server-side.
- **Build/run**: `npm run dev` local dev server only — no production build pipeline, CDN, or hosting
  concerns in scope.

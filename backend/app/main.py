from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import repository, schemas, stats
from app.config import get_settings
from app.database import connection_scope, init_db
from app.errors import ConflictError, NotFoundError
from app.openrag_integration import (
    ingest_match_summary_best_effort,
    ingest_video_analysis_best_effort,
)
from app.video_analysis import VideoAnalysisError, analyze_match_video

app = FastAPI(title="Table Tennis Match Stats API", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    messages = "; ".join(str(e["msg"]) for e in exc.errors())
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": messages}},
    )


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404, content={"error": {"code": "not_found", "message": str(exc)}}
    )


@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError):
    return JSONResponse(
        status_code=409, content={"error": {"code": "conflict", "message": str(exc)}}
    )


def _db():
    database_path = get_settings().database_path
    init_db(database_path)
    return connection_scope(database_path)


@app.post("/matches", response_model=schemas.Match, status_code=201, operation_id="createMatch")
async def create_match(payload: schemas.CreateMatchRequest):
    with _db() as conn:
        matchId = repository.create_match(
            conn,
            payload.player_one_name,
            payload.player_two_name,
            payload.points_to_win,
            payload.best_of,
        )
        return repository.serialize_match(conn, matchId)


@app.get("/matches", response_model=schemas.MatchListResponse, operation_id="listMatches")
async def list_matches(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    with _db() as conn:
        matches = repository.list_matches(conn, limit, offset)
    return {"matches": matches}


@app.get("/matches/{matchId}", response_model=schemas.Match, operation_id="getMatch")
async def get_match(matchId: int):
    with _db() as conn:
        return repository.serialize_match(conn, matchId)


@app.delete("/matches/{matchId}", status_code=204, operation_id="deleteMatch")
async def delete_match(matchId: int):
    with _db() as conn:
        repository.delete_match(conn, matchId)
    return None


@app.post("/matches/{matchId}/points", response_model=schemas.Match, operation_id="recordPoint")
async def record_point(matchId: int, payload: schemas.PointRequest):
    with _db() as conn:
        match_completed = repository.record_point(conn, matchId, payload.winner, payload.tag)
        result = repository.serialize_match(conn, matchId)
    if match_completed:
        await ingest_match_summary_best_effort(matchId)
    return result


@app.delete(
    "/matches/{matchId}/points/last", response_model=schemas.Match, operation_id="undoLastPoint"
)
async def undo_last_point(matchId: int):
    with _db() as conn:
        repository.undo_last_point(conn, matchId)
        return repository.serialize_match(conn, matchId)


@app.get(
    "/matches/{matchId}/summary", response_model=schemas.MatchSummary, operation_id="getMatchSummary"
)
async def get_match_summary(matchId: int):
    with _db() as conn:
        return stats.compute_summary(conn, matchId)


@app.post("/matches/{matchId}/abandon", status_code=204, operation_id="abandonMatch")
async def abandon_match(matchId: int):
    with _db() as conn:
        repository.abandon_match(conn, matchId)
    return None


@app.post("/matches/{matchId}/reset", response_model=schemas.Match, operation_id="resetMatch")
async def reset_match(matchId: int):
    with _db() as conn:
        repository.reset_match(conn, matchId)
        return repository.serialize_match(conn, matchId)


@app.post(
    "/video-analysis",
    response_model=schemas.VideoAnalysisResponse,
    operation_id="analyzeMatchVideo",
)
async def analyze_video(payload: schemas.VideoAnalysisRequest):
    """Standalone, best-effort AI estimate of match stats from a video URL.
    Never touches match/point data or the scoring engine — see video_analysis.py."""
    if not get_settings().gemini_enabled:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "video_analysis_disabled",
                    "message": "GEMINI_API_KEY is not configured on the backend",
                }
            },
        )
    try:
        result = await analyze_match_video(payload.video_url)
    except VideoAnalysisError as exc:
        return JSONResponse(
            status_code=502,
            content={"error": {"code": "video_analysis_failed", "message": str(exc)}},
        )
    if result.get("video_analyzable"):
        await ingest_video_analysis_best_effort(payload.video_url, result)
    return result

"""Best-effort RAG-index ingestion on match completion (REQ-019 side effect)
and on successful video analysis (REQ-029). Uses DataStax Astra DB's Data API
(`astrapy`) as the knowledge index: a plain-text summary is written to a
collection so a future feature (chat/search over history) can use it, but
ingestion failures — including missing/invalid Astra DB configuration, or the
Data API being unreachable — must never surface as an API error or block the
caller.
"""

import hashlib
import logging

from astrapy import DataAPIClient

from app import stats
from app.config import get_settings
from app.database import connection_scope, init_db

log = logging.getLogger(__name__)

COLLECTION_NAME = "rag_index"


def build_summary_text(summary: dict) -> str:
    p1 = summary["player_one"]["display_name"]
    p2 = summary["player_two"]["display_name"]

    lines = [
        f"Table Tennis Match #{summary['match_id']}: {p1} vs {p2}",
        f"Result: {summary['status']}",
    ]
    if summary["winner"]:
        winner_name = p1 if summary["winner"] == "player_one" else p2
        lines.append(f"Winner: {winner_name}")
    lines.append(
        f"Games won: {p1} {summary['games_won']['player_one']} - "
        f"{summary['games_won']['player_two']} {p2}"
    )
    lines.append("")
    lines.append("Games:")
    for g in summary["games"]:
        lines.append(
            f"  Game {g['game_number']}: {p1} {g['player_one_score']} - "
            f"{g['player_two_score']} {p2}"
        )
    lines.append("")
    for slot, name in (("player_one", p1), ("player_two", p2)):
        t = summary["totals"][slot]
        lines.append(
            f"{name}: {t['points_won']} points won, "
            f"serve win%={t['serve_points_won_percentage']}, "
            f"longest streak={t['longest_streak']}, "
            f"tags={t['tag_counts']}"
        )
    return "\n".join(lines)


def _get_collection(settings):
    client = DataAPIClient(token=settings.astra_db_application_token)
    database = client.get_async_database(settings.astra_db_api_endpoint)
    return database.get_collection(COLLECTION_NAME)


async def ingest_match_summary_best_effort(match_id: int) -> None:
    settings = get_settings()
    if not settings.astra_db_enabled:
        log.debug(
            "RAG ingestion skipped for match %s: Astra DB is not configured",
            match_id,
        )
        return

    init_db(settings.database_path)
    with connection_scope(settings.database_path) as conn:
        summary = stats.compute_summary(conn, match_id)
    summary_text = build_summary_text(summary)

    try:
        collection = _get_collection(settings)
        await collection.insert_one(
            {
                "kind": "match",
                "source_id": str(match_id),
                "content": summary_text,
            }
        )
    except Exception as exc:  # noqa: BLE001 - best-effort, must never propagate
        log.warning("Astra DB ingestion failed for match %s: %s", match_id, exc)


def build_video_analysis_text(video_url: str, analysis: dict) -> str:
    lines = [
        f"Video Match Analysis: {video_url}",
        f"Summary: {analysis['summary']}",
    ]
    if analysis.get("estimated_final_score"):
        lines.append(f"Estimated final score: {analysis['estimated_final_score']}")
    lines.append("")
    lines.append("Players:")
    for p in analysis.get("players", []):
        pts = p.get("estimated_points_won")
        lines.append(
            f"  {p['identifier']}: estimated points won="
            f"{pts if pts is not None else 'unknown'}, notes={p['notes']}"
        )
    if analysis.get("notable_moments"):
        lines.append("")
        lines.append("Notable moments:")
        for moment in analysis["notable_moments"]:
            lines.append(f"  - {moment}")
    lines.append("")
    lines.append(f"Confidence: {analysis['confidence']}")
    lines.append(f"Caveats: {analysis['caveats']}")
    return "\n".join(lines)


async def ingest_video_analysis_best_effort(video_url: str, analysis: dict) -> None:
    settings = get_settings()
    if not settings.astra_db_enabled:
        log.debug(
            "RAG ingestion skipped for video analysis of %s: Astra DB is not configured",
            video_url,
        )
        return

    summary_text = build_video_analysis_text(video_url, analysis)
    url_hash = hashlib.sha256(video_url.encode("utf-8")).hexdigest()[:16]

    try:
        collection = _get_collection(settings)
        await collection.insert_one(
            {
                "kind": "video_analysis",
                "source_id": url_hash,
                "video_url": video_url,
                "content": summary_text,
            }
        )
    except Exception as exc:  # noqa: BLE001 - best-effort, must never propagate
        log.warning("Astra DB ingestion failed for video analysis of %s: %s", video_url, exc)

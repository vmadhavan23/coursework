import sqlite3

from app.repository import (
    require_match_row,
    slot_for_player_id,
    get_games_won,
    get_player_row,
)


def _longest_streak(points: list[sqlite3.Row], player_id: int) -> int:
    longest = 0
    current = 0
    for p in points:
        if p["winner_player_id"] == player_id:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _player_totals(points: list[sqlite3.Row], player_id: int) -> dict:
    points_won = sum(1 for p in points if p["winner_player_id"] == player_id)
    served_points = [p for p in points if p["served_by_player_id"] == player_id]
    served_points_won = sum(1 for p in served_points if p["winner_player_id"] == player_id)
    serve_pct = (
        round(served_points_won / len(served_points) * 100) if served_points else None
    )
    tag_counts = {"ace": 0, "unforced_error": 0, "winner": 0}
    for p in points:
        if p["winner_player_id"] == player_id and p["tag"]:
            tag_counts[p["tag"]] += 1
    return {
        "points_won": points_won,
        "serve_points_won_percentage": serve_pct,
        "longest_streak": _longest_streak(points, player_id),
        "tag_counts": tag_counts,
    }


def compute_summary(conn: sqlite3.Connection, match_id: int) -> dict:
    m = require_match_row(conn, match_id)
    p1 = get_player_row(conn, m["player_one_id"])
    p2 = get_player_row(conn, m["player_two_id"])

    games_rows = conn.execute(
        "SELECT * FROM games WHERE match_id = ? ORDER BY game_number", (match_id,)
    ).fetchall()
    completed_games = [g for g in games_rows if g["winner_player_id"] is not None]

    game_stats = []
    for g in completed_games:
        winner_slot = slot_for_player_id(m, g["winner_player_id"])
        margin = abs(g["player_one_score"] - g["player_two_score"])
        game_stats.append(
            {
                "game_number": g["game_number"],
                "player_one_score": g["player_one_score"],
                "player_two_score": g["player_two_score"],
                "winner": winner_slot,
                "point_margin": margin,
            }
        )

    games_won_map = get_games_won(conn, match_id)
    winner_slot = (
        slot_for_player_id(m, m["winner_player_id"])
        if m["winner_player_id"] is not None
        else None
    )

    all_points = conn.execute(
        """SELECT points.* FROM points
           JOIN games ON points.game_id = games.id
           WHERE games.match_id = ?
           ORDER BY points.id""",
        (match_id,),
    ).fetchall()

    totals = {
        "player_one": _player_totals(all_points, m["player_one_id"]),
        "player_two": _player_totals(all_points, m["player_two_id"]),
    }

    closest_game = min(game_stats, key=lambda g: g["point_margin"]) if game_stats else None
    largest_margin_game = (
        max(game_stats, key=lambda g: g["point_margin"]) if game_stats else None
    )

    return {
        "match_id": m["id"],
        "player_one": {"id": p1["id"], "display_name": p1["display_name"]},
        "player_two": {"id": p2["id"], "display_name": p2["display_name"]},
        "status": m["status"],
        "winner": winner_slot,
        "games_won": {
            "player_one": games_won_map.get(m["player_one_id"], 0),
            "player_two": games_won_map.get(m["player_two_id"], 0),
        },
        "games": game_stats,
        "totals": totals,
        "closest_game": closest_game,
        "largest_margin_game": largest_margin_game,
    }

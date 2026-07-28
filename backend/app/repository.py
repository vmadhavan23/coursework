import sqlite3
from datetime import datetime, timezone

from app import scoring
from app.errors import ConflictError, NotFoundError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _player_slot_id(match_row: sqlite3.Row, slot: str) -> int:
    return match_row["player_one_id"] if slot == "player_one" else match_row["player_two_id"]


def slot_for_player_id(match_row: sqlite3.Row, player_id: int) -> str:
    return "player_one" if player_id == match_row["player_one_id"] else "player_two"


def get_or_create_player(conn: sqlite3.Connection, display_name: str) -> int:
    row = conn.execute(
        "SELECT id FROM players WHERE display_name = ?", (display_name,)
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO players (display_name, created_at) VALUES (?, ?)",
        (display_name, _now()),
    )
    return cur.lastrowid


def get_player_row(conn: sqlite3.Connection, player_id: int) -> sqlite3.Row:
    return conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()


def get_match_row(conn: sqlite3.Connection, match_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()


def require_match_row(conn: sqlite3.Connection, match_id: int) -> sqlite3.Row:
    m = get_match_row(conn, match_id)
    if m is None:
        raise NotFoundError(f"match {match_id} not found")
    return m


def get_current_game_row(conn: sqlite3.Connection, match_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM games WHERE match_id = ? ORDER BY game_number DESC LIMIT 1",
        (match_id,),
    ).fetchone()


def get_games_won(conn: sqlite3.Connection, match_id: int) -> dict[int, int]:
    rows = conn.execute(
        """SELECT winner_player_id, COUNT(*) AS c FROM games
           WHERE match_id = ? AND winner_player_id IS NOT NULL
           GROUP BY winner_player_id""",
        (match_id,),
    ).fetchall()
    return {r["winner_player_id"]: r["c"] for r in rows}


def create_match(
    conn: sqlite3.Connection,
    player_one_name: str,
    player_two_name: str,
    points_to_win: int,
    best_of: int,
) -> int:
    p1_id = get_or_create_player(conn, player_one_name)
    p2_id = get_or_create_player(conn, player_two_name)
    games_to_win = scoring.games_to_win_from_best_of(best_of)
    now = _now()

    cur = conn.execute(
        """INSERT INTO matches
               (player_one_id, player_two_id, points_to_win, games_to_win,
                status, serving_player_id, created_at)
           VALUES (?, ?, ?, ?, 'in_progress', ?, ?)""",
        (p1_id, p2_id, points_to_win, games_to_win, p1_id, now),
    )
    match_id = cur.lastrowid
    conn.execute("INSERT INTO games (match_id, game_number) VALUES (?, 1)", (match_id,))
    return match_id


def serialize_match(conn: sqlite3.Connection, match_id: int) -> dict:
    m = require_match_row(conn, match_id)
    p1 = get_player_row(conn, m["player_one_id"])
    p2 = get_player_row(conn, m["player_two_id"])
    game = get_current_game_row(conn, match_id)
    games_won_map = get_games_won(conn, match_id)
    games_to_win = m["games_to_win"]

    return {
        "id": m["id"],
        "player_one": {"id": p1["id"], "display_name": p1["display_name"]},
        "player_two": {"id": p2["id"], "display_name": p2["display_name"]},
        "points_to_win": m["points_to_win"],
        "best_of": scoring.best_of_from_games_to_win(games_to_win),
        "games_to_win": games_to_win,
        "status": m["status"],
        "current_game_number": game["game_number"] if game else 1,
        "current_score": {
            "player_one": game["player_one_score"] if game else 0,
            "player_two": game["player_two_score"] if game else 0,
        },
        "games_won": {
            "player_one": games_won_map.get(m["player_one_id"], 0),
            "player_two": games_won_map.get(m["player_two_id"], 0),
        },
        "serving_player": (
            slot_for_player_id(m, m["serving_player_id"])
            if m["serving_player_id"] is not None
            else None
        ),
        "winner": (
            slot_for_player_id(m, m["winner_player_id"])
            if m["winner_player_id"] is not None
            else None
        ),
        "created_at": m["created_at"],
        "completed_at": m["completed_at"],
    }


def record_point(
    conn: sqlite3.Connection, match_id: int, winner_slot: str, tag: str | None
) -> bool:
    """Returns True if this point completed the match."""
    m = require_match_row(conn, match_id)
    if m["status"] != "in_progress":
        raise ConflictError("match is not in progress")

    game = get_current_game_row(conn, match_id)
    winner_player_id = _player_slot_id(m, winner_slot)
    served_by_player_id = m["serving_player_id"]

    seq_row = conn.execute(
        "SELECT COUNT(*) AS c FROM points WHERE game_id = ?", (game["id"],)
    ).fetchone()
    sequence_number = seq_row["c"] + 1
    now = _now()

    conn.execute(
        """INSERT INTO points
               (game_id, sequence_number, winner_player_id, served_by_player_id, tag, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (game["id"], sequence_number, winner_player_id, served_by_player_id, tag, now),
    )

    if winner_slot == "player_one":
        new_p1, new_p2 = game["player_one_score"] + 1, game["player_two_score"]
    else:
        new_p1, new_p2 = game["player_one_score"], game["player_two_score"] + 1
    conn.execute(
        "UPDATE games SET player_one_score = ?, player_two_score = ? WHERE id = ?",
        (new_p1, new_p2, game["id"]),
    )

    game_win_slot = scoring.game_winner(new_p1, new_p2, m["points_to_win"])
    match_completed = False

    if game_win_slot:
        game_winner_player_id = _player_slot_id(m, game_win_slot)
        conn.execute(
            "UPDATE games SET winner_player_id = ?, completed_at = ? WHERE id = ?",
            (game_winner_player_id, now, game["id"]),
        )

        games_won_map = get_games_won(conn, match_id)
        p1_games = games_won_map.get(m["player_one_id"], 0)
        p2_games = games_won_map.get(m["player_two_id"], 0)
        match_win_slot = scoring.match_winner(p1_games, p2_games, m["games_to_win"])

        if match_win_slot:
            match_winner_player_id = _player_slot_id(m, match_win_slot)
            conn.execute(
                """UPDATE matches
                   SET status = 'completed', winner_player_id = ?, completed_at = ?,
                       serving_player_id = NULL
                   WHERE id = ?""",
                (match_winner_player_id, now, match_id),
            )
            match_completed = True
        else:
            next_game_number = game["game_number"] + 1
            conn.execute(
                "INSERT INTO games (match_id, game_number) VALUES (?, ?)",
                (match_id, next_game_number),
            )
            next_server_id = _player_slot_id(
                m, scoring.starting_server_for_game(next_game_number)
            )
            conn.execute(
                "UPDATE matches SET serving_player_id = ? WHERE id = ?",
                (next_server_id, match_id),
            )
    else:
        next_server_slot = scoring.server_for_next_point(
            game["game_number"], new_p1, new_p2, m["points_to_win"]
        )
        next_server_id = _player_slot_id(m, next_server_slot)
        conn.execute(
            "UPDATE matches SET serving_player_id = ? WHERE id = ?",
            (next_server_id, match_id),
        )

    return match_completed


def undo_last_point(conn: sqlite3.Connection, match_id: int) -> None:
    m = require_match_row(conn, match_id)

    last = conn.execute(
        """SELECT points.id AS point_id, points.winner_player_id,
                  games.id AS game_id, games.game_number,
                  games.winner_player_id AS game_winner_player_id,
                  games.player_one_score, games.player_two_score
           FROM points
           JOIN games ON points.game_id = games.id
           WHERE games.match_id = ?
           ORDER BY points.id DESC LIMIT 1""",
        (match_id,),
    ).fetchone()

    if last is None:
        raise ConflictError("no point to undo")

    if last["winner_player_id"] == m["player_one_id"]:
        new_p1, new_p2 = last["player_one_score"] - 1, last["player_two_score"]
    else:
        new_p1, new_p2 = last["player_one_score"], last["player_two_score"] - 1

    conn.execute("DELETE FROM points WHERE id = ?", (last["point_id"],))
    conn.execute(
        "UPDATE games SET player_one_score = ?, player_two_score = ? WHERE id = ?",
        (new_p1, new_p2, last["game_id"]),
    )

    if last["game_winner_player_id"] is not None:
        conn.execute(
            "UPDATE games SET winner_player_id = NULL, completed_at = NULL WHERE id = ?",
            (last["game_id"],),
        )
        conn.execute(
            "DELETE FROM games WHERE match_id = ? AND game_number = ?",
            (match_id, last["game_number"] + 1),
        )

    if m["status"] == "completed":
        conn.execute(
            """UPDATE matches
               SET status = 'in_progress', winner_player_id = NULL, completed_at = NULL
               WHERE id = ?""",
            (match_id,),
        )

    next_server_slot = scoring.server_for_next_point(
        last["game_number"], new_p1, new_p2, m["points_to_win"]
    )
    next_server_id = _player_slot_id(m, next_server_slot)
    conn.execute(
        "UPDATE matches SET serving_player_id = ? WHERE id = ?",
        (next_server_id, match_id),
    )


def abandon_match(conn: sqlite3.Connection, match_id: int) -> None:
    m = require_match_row(conn, match_id)
    if m["status"] != "in_progress":
        raise ConflictError("match is already completed and cannot be abandoned")
    conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))


def reset_match(conn: sqlite3.Connection, match_id: int) -> None:
    m = require_match_row(conn, match_id)
    if m["status"] != "in_progress":
        raise ConflictError("match is already completed and cannot be reset")

    conn.execute("DELETE FROM games WHERE match_id = ?", (match_id,))
    conn.execute("INSERT INTO games (match_id, game_number) VALUES (?, 1)", (match_id,))

    starting_id = _player_slot_id(m, scoring.starting_server_for_game(1))
    conn.execute(
        """UPDATE matches
           SET status = 'in_progress', winner_player_id = NULL, completed_at = NULL,
               serving_player_id = ?
           WHERE id = ?""",
        (starting_id, match_id),
    )


def list_matches(conn: sqlite3.Connection, limit: int, offset: int) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM matches WHERE status != 'in_progress'
           ORDER BY completed_at DESC, id DESC
           LIMIT ? OFFSET ?""",
        (limit, offset),
    ).fetchall()

    result = []
    for m in rows:
        p1 = get_player_row(conn, m["player_one_id"])
        p2 = get_player_row(conn, m["player_two_id"])
        games_won_map = get_games_won(conn, m["id"])
        winner_slot = (
            slot_for_player_id(m, m["winner_player_id"])
            if m["winner_player_id"] is not None
            else None
        )
        result.append(
            {
                "id": m["id"],
                "player_one": {"id": p1["id"], "display_name": p1["display_name"]},
                "player_two": {"id": p2["id"], "display_name": p2["display_name"]},
                "status": m["status"],
                "games_won": {
                    "player_one": games_won_map.get(m["player_one_id"], 0),
                    "player_two": games_won_map.get(m["player_two_id"], 0),
                },
                "winner": winner_slot,
                "created_at": m["created_at"],
                "completed_at": m["completed_at"],
            }
        )
    return result


def delete_match(conn: sqlite3.Connection, match_id: int) -> None:
    require_match_row(conn, match_id)
    conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))

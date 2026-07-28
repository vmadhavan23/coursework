import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_one_id INTEGER NOT NULL REFERENCES players(id),
    player_two_id INTEGER NOT NULL REFERENCES players(id),
    points_to_win INTEGER NOT NULL,
    games_to_win INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    serving_player_id INTEGER REFERENCES players(id),
    winner_player_id INTEGER REFERENCES players(id),
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    game_number INTEGER NOT NULL,
    player_one_score INTEGER NOT NULL DEFAULT 0,
    player_two_score INTEGER NOT NULL DEFAULT 0,
    winner_player_id INTEGER REFERENCES players(id),
    completed_at TEXT,
    UNIQUE (match_id, game_number)
);

CREATE TABLE IF NOT EXISTS points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    winner_player_id INTEGER NOT NULL REFERENCES players(id),
    served_by_player_id INTEGER NOT NULL REFERENCES players(id),
    tag TEXT CHECK (tag IN ('ace', 'unforced_error', 'winner')),
    created_at TEXT NOT NULL,
    UNIQUE (game_id, sequence_number)
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connection_scope(db_path: str):
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

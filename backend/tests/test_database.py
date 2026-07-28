from app.config import get_settings
from app.database import connection_scope, init_db


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", "/tmp/whatever.db")
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://example.apps.astra.datastax.com")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "secret")
    settings = get_settings()
    assert settings.database_path == "/tmp/whatever.db"
    assert settings.astra_db_api_endpoint == "https://example.apps.astra.datastax.com"
    assert settings.astra_db_application_token == "secret"
    assert settings.astra_db_enabled is True


def test_settings_astra_db_disabled_without_config(monkeypatch):
    monkeypatch.delenv("ASTRA_DB_API_ENDPOINT", raising=False)
    monkeypatch.delenv("ASTRA_DB_APPLICATION_TOKEN", raising=False)
    settings = get_settings()
    assert settings.astra_db_enabled is False


def test_schema_creates_tables_and_round_trips(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    with connection_scope(db_path) as conn:
        conn.execute(
            "INSERT INTO players (display_name, created_at) VALUES (?, ?)",
            ("Alice", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO players (display_name, created_at) VALUES (?, ?)",
            ("Bob", "2026-01-01T00:00:00"),
        )

    with connection_scope(db_path) as conn:
        rows = conn.execute("SELECT display_name FROM players ORDER BY id").fetchall()
        names = [r["display_name"] for r in rows]
    assert names == ["Alice", "Bob"]


def test_foreign_keys_enforced(tmp_path):
    db_path = str(tmp_path / "test_fk.db")
    init_db(db_path)

    with connection_scope(db_path) as conn:
        cur = conn.execute("PRAGMA foreign_keys")
        assert cur.fetchone()[0] == 1


def test_duplicate_player_name_rejected(tmp_path):
    import sqlite3

    db_path = str(tmp_path / "test_dupe.db")
    init_db(db_path)

    with connection_scope(db_path) as conn:
        conn.execute(
            "INSERT INTO players (display_name, created_at) VALUES (?, ?)",
            ("Alice", "2026-01-01T00:00:00"),
        )

    try:
        with connection_scope(db_path) as conn:
            conn.execute(
                "INSERT INTO players (display_name, created_at) VALUES (?, ?)",
                ("Alice", "2026-01-01T00:00:00"),
            )
        assert False, "expected IntegrityError"
    except sqlite3.IntegrityError:
        pass


def test_game_cascade_delete_on_match_delete(tmp_path):
    db_path = str(tmp_path / "test_cascade.db")
    init_db(db_path)

    with connection_scope(db_path) as conn:
        conn.execute(
            "INSERT INTO players (display_name, created_at) VALUES (?, ?)",
            ("Alice", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO players (display_name, created_at) VALUES (?, ?)",
            ("Bob", "2026-01-01T00:00:00"),
        )
        conn.execute(
            """INSERT INTO matches
               (player_one_id, player_two_id, points_to_win, games_to_win, status, created_at)
               VALUES (1, 2, 11, 2, 'in_progress', ?)""",
            ("2026-01-01T00:00:00",),
        )
        conn.execute(
            "INSERT INTO games (match_id, game_number) VALUES (1, 1)"
        )

    with connection_scope(db_path) as conn:
        conn.execute("DELETE FROM matches WHERE id = 1")

    with connection_scope(db_path) as conn:
        remaining = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert remaining == 0

import pytest
from openrag_sdk import OpenRAGError

from app import repository
from app.database import connection_scope, init_db
from app.openrag_integration import build_summary_text, ingest_match_summary_best_effort


class FakeDocumentsClient:
    def __init__(self, should_raise=False):
        self.should_raise = should_raise
        self.calls = []

    async def ingest(self, file=None, filename=None, **kwargs):
        content = file.read().decode("utf-8") if file else None
        self.calls.append({"filename": filename, "content": content})
        if self.should_raise:
            raise OpenRAGError("simulated OpenRAG failure")


class FakeOpenRAGClient:
    """Records constructor args/instances so tests can assert on them."""

    last_instance: "FakeOpenRAGClient | None" = None

    def __init__(self, api_key=None, base_url=None, should_raise=False, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.documents = FakeDocumentsClient(should_raise=should_raise)
        FakeOpenRAGClient.last_instance = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def make_completed_match(tmp_path):
    db_path = str(tmp_path / "openrag_test.db")
    init_db(db_path)
    with connection_scope(db_path) as conn:
        match_id = repository.create_match(conn, "Alice", "Bob", 11, 1)
        for _ in range(11):
            repository.record_point(conn, match_id, "player_one", None)
    return db_path, match_id


def test_build_summary_text_contains_key_fields():
    summary = {
        "match_id": 7,
        "player_one": {"id": 1, "display_name": "Alice"},
        "player_two": {"id": 2, "display_name": "Bob"},
        "status": "completed",
        "winner": "player_one",
        "games_won": {"player_one": 1, "player_two": 0},
        "games": [
            {
                "game_number": 1,
                "player_one_score": 11,
                "player_two_score": 2,
                "winner": "player_one",
                "point_margin": 9,
            }
        ],
        "totals": {
            "player_one": {
                "points_won": 11,
                "serve_points_won_percentage": 100,
                "longest_streak": 6,
                "tag_counts": {"ace": 1, "unforced_error": 0, "winner": 1},
            },
            "player_two": {
                "points_won": 2,
                "serve_points_won_percentage": 33,
                "longest_streak": 1,
                "tag_counts": {"ace": 0, "unforced_error": 1, "winner": 0},
            },
        },
        "closest_game": None,
        "largest_margin_game": None,
    }
    text = build_summary_text(summary)
    assert "Match #7" in text
    assert "Alice vs Bob" in text
    assert "Winner: Alice" in text
    assert "Game 1: Alice 11 - 2 Bob" in text
    assert "longest streak=6" in text


@pytest.mark.asyncio
async def test_ingestion_skipped_without_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENRAG_API_KEY", "")
    monkeypatch.setattr("app.openrag_integration.OpenRAGClient", FakeOpenRAGClient)
    FakeOpenRAGClient.last_instance = None

    # Even a nonexistent match_id must not raise: the function should return
    # before ever touching the database or constructing a client.
    await ingest_match_summary_best_effort(999999)

    assert FakeOpenRAGClient.last_instance is None


@pytest.mark.asyncio
async def test_ingestion_success_calls_documents_ingest(monkeypatch, tmp_path):
    db_path, match_id = make_completed_match(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("OPENRAG_API_KEY", "test-key")
    monkeypatch.setenv("OPENRAG_URL", "http://example.test")
    monkeypatch.setattr("app.openrag_integration.OpenRAGClient", FakeOpenRAGClient)
    FakeOpenRAGClient.last_instance = None

    await ingest_match_summary_best_effort(match_id)

    instance = FakeOpenRAGClient.last_instance
    assert instance is not None
    assert instance.api_key == "test-key"
    assert instance.base_url == "http://example.test"
    assert len(instance.documents.calls) == 1
    call = instance.documents.calls[0]
    assert call["filename"] == f"match-{match_id}.txt"
    assert "Alice vs Bob" in call["content"]


@pytest.mark.asyncio
async def test_ingestion_failure_is_swallowed(monkeypatch, tmp_path):
    db_path, match_id = make_completed_match(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("OPENRAG_API_KEY", "test-key")

    def failing_client(*args, **kwargs):
        return FakeOpenRAGClient(*args, should_raise=True, **kwargs)

    monkeypatch.setattr("app.openrag_integration.OpenRAGClient", failing_client)

    # Must not raise, even though the fake client's ingest() raises OpenRAGError.
    await ingest_match_summary_best_effort(match_id)


def test_full_api_flow_triggers_ingestion_on_match_completion(client, monkeypatch):
    """End-to-end: completing a match through the real HTTP API triggers the
    OpenRAG ingestion hook, and the request still succeeds regardless."""
    monkeypatch.setattr("app.openrag_integration.OpenRAGClient", FakeOpenRAGClient)
    FakeOpenRAGClient.last_instance = None
    monkeypatch.setenv("OPENRAG_API_KEY", "test-key")

    resp = client.post(
        "/matches",
        json={
            "player_one_name": "Alice",
            "player_two_name": "Bob",
            "points_to_win": 11,
            "best_of": 1,
        },
    )
    match_id = resp.json()["id"]

    for _ in range(11):
        resp = client.post(f"/matches/{match_id}/points", json={"winner": "player_one"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    instance = FakeOpenRAGClient.last_instance
    assert instance is not None
    assert len(instance.documents.calls) == 1
    assert instance.documents.calls[0]["filename"] == f"match-{match_id}.txt"


def test_full_api_flow_match_completes_even_if_ingestion_fails(client, monkeypatch):
    """The HTTP response must not be affected by an OpenRAG ingestion failure."""

    def failing_client(*args, **kwargs):
        return FakeOpenRAGClient(*args, should_raise=True, **kwargs)

    monkeypatch.setattr("app.openrag_integration.OpenRAGClient", failing_client)
    monkeypatch.setenv("OPENRAG_API_KEY", "test-key")

    resp = client.post(
        "/matches",
        json={
            "player_one_name": "Alice",
            "player_two_name": "Bob",
            "points_to_win": 11,
            "best_of": 1,
        },
    )
    match_id = resp.json()["id"]

    for _ in range(11):
        resp = client.post(f"/matches/{match_id}/points", json={"winner": "player_one"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

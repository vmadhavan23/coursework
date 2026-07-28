import pytest

from app import repository
from app.database import connection_scope, init_db
from app.rag_integration import (
    build_summary_text,
    build_video_analysis_text,
    ingest_match_summary_best_effort,
    ingest_video_analysis_best_effort,
)


class FakeCollection:
    def __init__(self, should_raise=False):
        self.should_raise = should_raise
        self.calls = []

    async def insert_one(self, document, **kwargs):
        self.calls.append(document)
        if self.should_raise:
            raise RuntimeError("simulated Astra DB failure")


class FakeDatabase:
    def __init__(self, collection):
        self._collection = collection

    def get_collection(self, name, **kwargs):
        return self._collection


class FakeDataAPIClient:
    """Records constructor args/instances so tests can assert on them."""

    last_instance: "FakeDataAPIClient | None" = None

    def __init__(self, token=None, should_raise=False, **kwargs):
        self.token = token
        self.api_endpoint = None
        self.collection = FakeCollection(should_raise=should_raise)
        self.database = FakeDatabase(self.collection)
        FakeDataAPIClient.last_instance = self

    def get_async_database(self, api_endpoint, **kwargs):
        self.api_endpoint = api_endpoint
        return self.database


def make_completed_match(tmp_path):
    db_path = str(tmp_path / "rag_test.db")
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
async def test_ingestion_skipped_without_astra_config(monkeypatch, tmp_path):
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "")
    monkeypatch.setattr("app.rag_integration.DataAPIClient", FakeDataAPIClient)
    FakeDataAPIClient.last_instance = None

    # Even a nonexistent match_id must not raise: the function should return
    # before ever touching the database or constructing a client.
    await ingest_match_summary_best_effort(999999)

    assert FakeDataAPIClient.last_instance is None


@pytest.mark.asyncio
async def test_ingestion_success_calls_insert_one(monkeypatch, tmp_path):
    db_path, match_id = make_completed_match(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://test.apps.astra.datastax.com")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "test-token")
    monkeypatch.setattr("app.rag_integration.DataAPIClient", FakeDataAPIClient)
    FakeDataAPIClient.last_instance = None

    await ingest_match_summary_best_effort(match_id)

    instance = FakeDataAPIClient.last_instance
    assert instance is not None
    assert instance.token == "test-token"
    assert instance.api_endpoint == "https://test.apps.astra.datastax.com"
    assert len(instance.collection.calls) == 1
    doc = instance.collection.calls[0]
    assert doc["kind"] == "match"
    assert doc["source_id"] == str(match_id)
    assert "Alice vs Bob" in doc["content"]


@pytest.mark.asyncio
async def test_ingestion_failure_is_swallowed(monkeypatch, tmp_path):
    db_path, match_id = make_completed_match(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://test.apps.astra.datastax.com")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "test-token")

    def failing_client(*args, **kwargs):
        return FakeDataAPIClient(*args, should_raise=True, **kwargs)

    monkeypatch.setattr("app.rag_integration.DataAPIClient", failing_client)

    # Must not raise, even though the fake collection's insert_one() raises.
    await ingest_match_summary_best_effort(match_id)


def test_full_api_flow_triggers_ingestion_on_match_completion(client, monkeypatch):
    """End-to-end: completing a match through the real HTTP API triggers the
    Astra DB ingestion hook, and the request still succeeds regardless."""
    monkeypatch.setattr("app.rag_integration.DataAPIClient", FakeDataAPIClient)
    FakeDataAPIClient.last_instance = None
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://test.apps.astra.datastax.com")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "test-token")

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

    instance = FakeDataAPIClient.last_instance
    assert instance is not None
    assert len(instance.collection.calls) == 1
    assert instance.collection.calls[0]["source_id"] == str(match_id)


def test_full_api_flow_match_completes_even_if_ingestion_fails(client, monkeypatch):
    """The HTTP response must not be affected by an Astra DB ingestion failure."""

    def failing_client(*args, **kwargs):
        return FakeDataAPIClient(*args, should_raise=True, **kwargs)

    monkeypatch.setattr("app.rag_integration.DataAPIClient", failing_client)
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://test.apps.astra.datastax.com")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "test-token")

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


def _sample_video_analysis():
    return {
        "video_analyzable": True,
        "summary": "A close singles match.",
        "players": [
            {"identifier": "Player in blue", "estimated_points_won": 11, "notes": "Strong serve"},
            {"identifier": "Player in red", "estimated_points_won": 9, "notes": "Fought back"},
        ],
        "estimated_final_score": "11-9",
        "notable_moments": ["Long rally at 9-9"],
        "confidence": "medium",
        "caveats": "Scoreboard partially obscured at times.",
    }


def test_build_video_analysis_text_contains_key_fields():
    text = build_video_analysis_text("https://www.youtube.com/watch?v=abc123", _sample_video_analysis())
    assert "https://www.youtube.com/watch?v=abc123" in text
    assert "A close singles match." in text
    assert "Estimated final score: 11-9" in text
    assert "Player in blue: estimated points won=11, notes=Strong serve" in text
    assert "Long rally at 9-9" in text
    assert "Confidence: medium" in text
    assert "Caveats: Scoreboard partially obscured at times." in text


@pytest.mark.asyncio
async def test_video_ingestion_skipped_without_astra_config(monkeypatch):
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "")
    monkeypatch.setattr("app.rag_integration.DataAPIClient", FakeDataAPIClient)
    FakeDataAPIClient.last_instance = None

    await ingest_video_analysis_best_effort(
        "https://www.youtube.com/watch?v=abc123", _sample_video_analysis()
    )

    assert FakeDataAPIClient.last_instance is None


@pytest.mark.asyncio
async def test_video_ingestion_success_calls_insert_one(monkeypatch):
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://test.apps.astra.datastax.com")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "test-token")
    monkeypatch.setattr("app.rag_integration.DataAPIClient", FakeDataAPIClient)
    FakeDataAPIClient.last_instance = None

    video_url = "https://www.youtube.com/watch?v=abc123"
    await ingest_video_analysis_best_effort(video_url, _sample_video_analysis())

    instance = FakeDataAPIClient.last_instance
    assert instance is not None
    assert instance.token == "test-token"
    assert len(instance.collection.calls) == 1
    doc = instance.collection.calls[0]
    assert doc["kind"] == "video_analysis"
    assert doc["video_url"] == video_url
    assert "A close singles match." in doc["content"]


@pytest.mark.asyncio
async def test_video_ingestion_failure_is_swallowed(monkeypatch):
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://test.apps.astra.datastax.com")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "test-token")

    def failing_client(*args, **kwargs):
        return FakeDataAPIClient(*args, should_raise=True, **kwargs)

    monkeypatch.setattr("app.rag_integration.DataAPIClient", failing_client)

    # Must not raise, even though the fake collection's insert_one() raises.
    await ingest_video_analysis_best_effort(
        "https://www.youtube.com/watch?v=abc123", _sample_video_analysis()
    )

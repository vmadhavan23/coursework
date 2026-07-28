import json

import pytest

from app.video_analysis import VideoAnalysisError, analyze_match_video


class FakeModels:
    def __init__(self, response_text=None, should_raise=False):
        self.response_text = response_text
        self.should_raise = should_raise
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.should_raise:
            raise RuntimeError("simulated Gemini failure")

        class FakeResponse:
            text = self.response_text

        return FakeResponse()


class FakeAio:
    def __init__(self, models):
        self.models = models


class FakeGenAIClient:
    last_instance = None

    def __init__(self, api_key=None, response_text=None, should_raise=False):
        self.api_key = api_key
        models = FakeModels(response_text=response_text, should_raise=should_raise)
        self.aio = FakeAio(models)
        FakeGenAIClient.last_instance = self


def _sample_payload():
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


@pytest.mark.asyncio
async def test_analysis_disabled_without_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(VideoAnalysisError, match="not configured"):
        await analyze_match_video("https://example.com/video.mp4")


@pytest.mark.asyncio
async def test_analysis_success(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    payload = _sample_payload()

    def make_client(api_key=None):
        return FakeGenAIClient(api_key=api_key, response_text=json.dumps(payload))

    monkeypatch.setattr("app.video_analysis.genai.Client", make_client)

    result = await analyze_match_video("https://www.youtube.com/watch?v=abc123")

    assert result == payload
    instance = FakeGenAIClient.last_instance
    assert instance.api_key == "test-key"
    call = instance.aio.models.calls[0]
    assert call["model"] == "gemini-flash-latest"
    file_data_part = call["contents"].parts[0]
    assert file_data_part.file_data.file_uri == "https://www.youtube.com/watch?v=abc123"


@pytest.mark.asyncio
async def test_analysis_failure_wrapped(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def make_client(api_key=None):
        return FakeGenAIClient(api_key=api_key, should_raise=True)

    monkeypatch.setattr("app.video_analysis.genai.Client", make_client)

    with pytest.raises(VideoAnalysisError, match="simulated Gemini failure"):
        await analyze_match_video("https://example.com/video.mp4")


def test_api_rejects_invalid_url_scheme(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    resp = client.post("/video-analysis", json={"video_url": "not-a-url"})
    assert resp.status_code == 422


def test_api_returns_503_when_disabled(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    resp = client.post("/video-analysis", json={"video_url": "https://example.com/video.mp4"})
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "video_analysis_disabled"


def test_api_success(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    payload = _sample_payload()

    def make_client(api_key=None):
        return FakeGenAIClient(api_key=api_key, response_text=json.dumps(payload))

    monkeypatch.setattr("app.video_analysis.genai.Client", make_client)

    resp = client.post(
        "/video-analysis", json={"video_url": "https://www.youtube.com/watch?v=abc123"}
    )
    assert resp.status_code == 200
    assert resp.json() == payload


def test_api_returns_502_on_gemini_failure(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def make_client(api_key=None):
        return FakeGenAIClient(api_key=api_key, should_raise=True)

    monkeypatch.setattr("app.video_analysis.genai.Client", make_client)

    resp = client.post(
        "/video-analysis", json={"video_url": "https://www.youtube.com/watch?v=abc123"}
    )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "video_analysis_failed"


def test_api_ingests_summary_into_rag_index_when_analyzable(client, monkeypatch):
    """REQ-029: a successful analysis is added to the RAG index, best-effort."""
    from tests.test_rag_integration import FakeDataAPIClient

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://test.apps.astra.datastax.com")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "test-token")
    monkeypatch.setattr("app.rag_integration.DataAPIClient", FakeDataAPIClient)
    FakeDataAPIClient.last_instance = None

    payload = _sample_payload()

    def make_client(api_key=None):
        return FakeGenAIClient(api_key=api_key, response_text=json.dumps(payload))

    monkeypatch.setattr("app.video_analysis.genai.Client", make_client)

    video_url = "https://www.youtube.com/watch?v=abc123"
    resp = client.post("/video-analysis", json={"video_url": video_url})
    assert resp.status_code == 200

    instance = FakeDataAPIClient.last_instance
    assert instance is not None
    assert len(instance.collection.calls) == 1
    assert instance.collection.calls[0]["video_url"] == video_url


def test_api_skips_ingestion_when_not_analyzable(client, monkeypatch):
    """REQ-029: a video that could not be analyzed must not be added to the index."""
    from tests.test_rag_integration import FakeDataAPIClient

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://test.apps.astra.datastax.com")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "test-token")
    monkeypatch.setattr("app.rag_integration.DataAPIClient", FakeDataAPIClient)
    FakeDataAPIClient.last_instance = None

    payload = {
        "video_analyzable": False,
        "summary": "This is a cooking video, not a table tennis match.",
        "players": [],
        "estimated_final_score": None,
        "notable_moments": [],
        "confidence": "low",
        "caveats": "Not a table tennis match.",
    }

    def make_client(api_key=None):
        return FakeGenAIClient(api_key=api_key, response_text=json.dumps(payload))

    monkeypatch.setattr("app.video_analysis.genai.Client", make_client)

    resp = client.post(
        "/video-analysis", json={"video_url": "https://www.youtube.com/watch?v=notpingpong"}
    )
    assert resp.status_code == 200
    assert FakeDataAPIClient.last_instance is None

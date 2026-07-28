import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "")
    monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "")
    with TestClient(app) as c:
        yield c

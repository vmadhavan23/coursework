import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


@dataclass(frozen=True)
class Settings:
    database_path: str
    astra_db_api_endpoint: str | None
    astra_db_application_token: str | None
    gemini_api_key: str | None

    @property
    def astra_db_enabled(self) -> bool:
        return bool(self.astra_db_api_endpoint and self.astra_db_application_token)

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)


def get_settings() -> Settings:
    return Settings(
        database_path=os.environ.get("DATABASE_PATH", "./tabletennis.db"),
        astra_db_api_endpoint=os.environ.get("ASTRA_DB_API_ENDPOINT") or None,
        astra_db_application_token=os.environ.get("ASTRA_DB_APPLICATION_TOKEN") or None,
        gemini_api_key=os.environ.get("GEMINI_API_KEY") or None,
    )

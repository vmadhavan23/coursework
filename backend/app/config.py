import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


@dataclass(frozen=True)
class Settings:
    database_path: str
    openrag_url: str | None
    openrag_api_key: str | None

    @property
    def openrag_enabled(self) -> bool:
        return bool(self.openrag_api_key)


def get_settings() -> Settings:
    return Settings(
        database_path=os.environ.get("DATABASE_PATH", "./tabletennis.db"),
        openrag_url=os.environ.get("OPENRAG_URL") or None,
        openrag_api_key=os.environ.get("OPENRAG_API_KEY") or None,
    )

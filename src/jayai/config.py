from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
TEMPLATES_DIR = PROJECT_ROOT / "src" / "jayai" / "templates"


def _default_sqlite_url() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = (DATA_DIR / "jayai.db").resolve()
    return f"sqlite:///{db_path.as_posix()}"


@dataclass(frozen=True)
class Settings:
    app_name: str
    database_url: str
    templates_dir: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("JAYAI_APP_NAME", "JayAI"),
        database_url=os.getenv("JAYAI_DATABASE_URL", _default_sqlite_url()),
        templates_dir=TEMPLATES_DIR,
    )

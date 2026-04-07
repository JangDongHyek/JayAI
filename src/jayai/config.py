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
    data_dir: Path
    runs_dir: Path
    local_config_path: Path
    templates_dir: Path
    base_path: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    base_path = os.getenv("JAYAI_BASE_PATH", "").strip()
    if base_path in {"", "/"}:
        base_path = ""
    elif not base_path.startswith("/"):
        base_path = f"/{base_path}"
    base_path = base_path.rstrip("/")
    return Settings(
        app_name=os.getenv("JAYAI_APP_NAME", "JayAI"),
        database_url=os.getenv("JAYAI_DATABASE_URL", _default_sqlite_url()),
        data_dir=DATA_DIR,
        runs_dir=DATA_DIR / "runs",
        local_config_path=DATA_DIR / "local-config.json",
        templates_dir=TEMPLATES_DIR,
        base_path=base_path,
    )

from __future__ import annotations

import json
import os
from pathlib import Path

from ..config import get_settings


settings = get_settings()


def _normalize_server_url(value: str) -> str:
    normalized = value.strip()
    while normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def read_local_config() -> dict[str, str]:
    default_url = _normalize_server_url(os.getenv("JAYAI_SERVER_URL", ""))
    path = settings.local_config_path
    if not path.exists():
        return {"server_url": default_url}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("server_url", default_url)
    payload["server_url"] = _normalize_server_url(payload.get("server_url", ""))
    return payload


def write_local_config(server_url: str) -> dict[str, str]:
    payload = {"server_url": _normalize_server_url(server_url)}
    path = settings.local_config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def get_server_url() -> str:
    config = read_local_config()
    server_url = _normalize_server_url(config.get("server_url", ""))
    if not server_url:
        raise RuntimeError("server_url is not configured")
    return server_url

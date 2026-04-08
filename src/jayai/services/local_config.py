from __future__ import annotations

import json
import socket
from pathlib import Path

from ..config import get_settings


DEFAULT_SERVER_URL = "http://43.203.252.40/jayai-api"

settings = get_settings()


def _default_device_name() -> str:
    return socket.gethostname().lower()


def _normalize_device_name(value: str | None) -> str:
    name = (value or "").strip()
    return name or _default_device_name()


def _read_raw_payload(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def read_local_config() -> dict[str, str]:
    path = settings.local_config_path
    payload = _read_raw_payload(path)
    return {
        "server_url": DEFAULT_SERVER_URL,
        "device_name": _normalize_device_name(payload.get("device_name")),
    }


def write_local_config(*, device_name: str) -> dict[str, str]:
    payload = {
        "server_url": DEFAULT_SERVER_URL,
        "device_name": _normalize_device_name(device_name),
    }
    path = settings.local_config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def ensure_local_config() -> dict[str, str]:
    payload = read_local_config()
    path = settings.local_config_path
    current = _read_raw_payload(path)
    if current != payload:
        write_local_config(device_name=payload["device_name"])
    return payload


def get_server_url() -> str:
    return DEFAULT_SERVER_URL

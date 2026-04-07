from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class ServerApiError(RuntimeError):
    pass


class ServerClient:
    def __init__(self, server_url: str) -> None:
        self.server_url = server_url.rstrip("/")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            f"{self.server_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=900) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ServerApiError(f"server {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ServerApiError(f"server unreachable: {exc.reason}") from exc

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/health")

    def list_projects(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/projects")

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/projects", payload)

    def get_project(self, project_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/projects/{project_id}")

    def register_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/devices", payload)

    def list_bindings(self, project_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/projects/{project_id}/bindings")

    def bind_workspace(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/api/projects/{project_id}/bindings", payload)

    def list_conversations(self, project_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/projects/{project_id}/conversations")

    def create_conversation(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/api/projects/{project_id}/conversations", payload)

    def get_conversation(self, conversation_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/projects/conversations/{conversation_id}")

    def list_messages(self, conversation_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/projects/conversations/{conversation_id}/messages")

    def create_message(self, conversation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/api/projects/conversations/{conversation_id}/messages", payload)

    def create_messages_bulk(
        self,
        conversation_id: int,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._request(
            "POST",
            f"/api/projects/conversations/{conversation_id}/messages/bulk",
            payload,
        )

    def create_run(self, conversation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/api/projects/conversations/{conversation_id}/runs", payload)

    def update_run(self, run_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/api/projects/runs/{run_id}", payload)

from __future__ import annotations

import platform
import socket
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException

from ..schemas import (
    ConversationCreate,
    ConversationExecuteRequest,
    ConversationExecuteResponse,
    ConversationRead,
    DeviceRead,
    LocalConfigRead,
    LocalConfigWrite,
    LocalStatusResponse,
    MessageRead,
    ProjectCreate,
    ProjectRead,
    RunnerProbeRequest,
    RunnerProbeResponse,
    RunRead,
    WorkspaceBindingCreate,
    WorkspaceBindingRead,
    WorkspaceScanRequest,
    WorkspaceScanResponse,
)
from ..services.local_config import get_server_url, read_local_config, write_local_config
from ..services.orchestrator import execute_user_task
from ..services.runner import probe_local_environment, scan_workspace
from ..services.server_api import ServerApiError, ServerClient


router = APIRouter()


def _local_device_payload() -> dict[str, object]:
    return {
        "name": socket.gethostname().lower(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "is_server": False,
    }


def _server_client() -> ServerClient:
    return ServerClient(get_server_url())


def _register_local_device(client: ServerClient) -> dict[str, object]:
    return client.register_device(_local_device_payload())


def _resolve_workspace_path(
    client: ServerClient,
    *,
    project_id: int,
    device_id: int,
    workspace_path: str | None,
) -> str:
    if workspace_path:
        resolved = str(Path(workspace_path).expanduser().resolve())
        client.bind_workspace(
            project_id,
            {
                "project_id": project_id,
                "device_id": device_id,
                "local_path": resolved,
                "preferred_branch": None,
            },
        )
        return resolved

    bindings = client.list_bindings(project_id)
    own_binding = next((item for item in bindings if item["device_id"] == device_id), None)
    if own_binding:
        return own_binding["local_path"]
    if bindings:
        return bindings[0]["local_path"]
    raise HTTPException(status_code=400, detail="workspace path required")


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local"}


@router.get("/api/local/config", response_model=LocalConfigRead)
def get_local_config() -> LocalConfigRead:
    return LocalConfigRead(**read_local_config())


@router.post("/api/local/config", response_model=LocalConfigRead)
def save_local_config(payload: LocalConfigWrite) -> LocalConfigRead:
    return LocalConfigRead(**write_local_config(payload.server_url))


@router.get("/api/local/status", response_model=LocalStatusResponse)
def local_status() -> LocalStatusResponse:
    config = read_local_config()
    server_url = config.get("server_url", "")
    server_reachable = False
    if server_url:
        try:
            server_reachable = ServerClient(server_url).health().get("status") == "ok"
        except ServerApiError:
            server_reachable = False
    return LocalStatusResponse(
        server_url=server_url,
        server_reachable=server_reachable,
        local_device_name=socket.gethostname().lower(),
        local_hostname=socket.gethostname(),
        local_platform=platform.platform(),
    )


@router.post("/api/devices/local", response_model=DeviceRead)
def register_local_device() -> DeviceRead:
    try:
        device = _register_local_device(_server_client())
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DeviceRead.model_validate(device)


@router.post("/api/runner/probe", response_model=RunnerProbeResponse)
def probe_runner(payload: RunnerProbeRequest) -> RunnerProbeResponse:
    return probe_local_environment(payload.workdir)


@router.post("/api/runner/scan-workspace", response_model=WorkspaceScanResponse)
def scan_runner_workspace(payload: WorkspaceScanRequest) -> WorkspaceScanResponse:
    return scan_workspace(payload.path)


@router.get("/api/projects", response_model=list[ProjectRead])
def list_projects() -> list[ProjectRead]:
    try:
        projects = _server_client().list_projects()
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [ProjectRead.model_validate(project) for project in projects]


@router.post("/api/projects", response_model=ProjectRead)
def create_project(payload: ProjectCreate) -> ProjectRead:
    try:
        project = _server_client().create_project(payload.model_dump())
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProjectRead.model_validate(project)


@router.get("/api/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: int) -> ProjectRead:
    try:
        project = _server_client().get_project(project_id)
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProjectRead.model_validate(project)


@router.get("/api/projects/{project_id}/bindings", response_model=list[WorkspaceBindingRead])
def list_bindings(project_id: int) -> list[WorkspaceBindingRead]:
    try:
        bindings = _server_client().list_bindings(project_id)
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [WorkspaceBindingRead.model_validate(binding) for binding in bindings]


@router.post("/api/projects/{project_id}/bindings", response_model=WorkspaceBindingRead)
def bind_workspace(project_id: int, payload: WorkspaceBindingCreate) -> WorkspaceBindingRead:
    try:
        binding_payload = payload.model_dump()
        binding_payload["local_path"] = str(Path(payload.local_path).expanduser().resolve())
        binding = _server_client().bind_workspace(project_id, binding_payload)
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkspaceBindingRead.model_validate(binding)


@router.get("/api/projects/{project_id}/conversations", response_model=list[ConversationRead])
def list_conversations(project_id: int) -> list[ConversationRead]:
    try:
        conversations = _server_client().list_conversations(project_id)
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [ConversationRead.model_validate(item) for item in conversations]


@router.post("/api/projects/{project_id}/conversations", response_model=ConversationRead)
def create_conversation(project_id: int, payload: ConversationCreate) -> ConversationRead:
    try:
        conversation = _server_client().create_conversation(project_id, payload.model_dump())
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ConversationRead.model_validate(conversation)


@router.get("/api/projects/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(conversation_id: int) -> list[MessageRead]:
    try:
        messages = _server_client().list_messages(conversation_id)
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [MessageRead.model_validate(message) for message in messages]


@router.post(
    "/api/projects/conversations/{conversation_id}/execute",
    response_model=ConversationExecuteResponse,
)
def execute_conversation(
    conversation_id: int,
    payload: ConversationExecuteRequest,
) -> ConversationExecuteResponse:
    try:
        client = _server_client()
        device = _register_local_device(client)
        conversation = client.get_conversation(conversation_id)
        project = client.get_project(conversation["project_id"])
        workspace_path = _resolve_workspace_path(
            client,
            project_id=project["id"],
            device_id=device["id"],
            workspace_path=payload.workspace_path,
        )

        client.create_message(
            conversation_id,
            {
                "role": "user",
                "agent": None,
                "content": payload.content,
                "model_hint": None,
            },
        )
        run = client.create_run(
            conversation_id,
            {
                "device_id": device["id"],
                "strategy": "pending",
                "status": "running",
                "prompt_excerpt": payload.content[:500],
                "result_summary": None,
            },
        )
        result = execute_user_task(
            project=SimpleNamespace(**project),
            workspace_path=workspace_path,
            prompt=payload.content,
        )

        assistant_messages: list[dict[str, object]] = []
        if result.codex and result.codex.final:
            assistant_messages.append(
                {
                    "role": "assistant",
                    "agent": "codex",
                    "content": result.codex.final,
                    "model_hint": "codex",
                }
            )
        if result.claude:
            claude_content = "\n\n".join(
                part
                for part in [
                    result.claude.final,
                    f"[CRITIQUE]\n{result.claude.critique}" if result.claude.critique else "",
                    f"[FOLLOW_UP]\n{result.claude.follow_up}" if result.claude.follow_up else "",
                ]
                if part
            ).strip()
            if claude_content:
                assistant_messages.append(
                    {
                        "role": "assistant",
                        "agent": "claude",
                        "content": claude_content,
                        "model_hint": "claude",
                    }
                )
        assistant_messages.append(
            {
                "role": "assistant",
                "agent": "jayai",
                "content": result.summary or "Run completed.",
                "model_hint": result.strategy,
            }
        )

        created_messages = client.create_messages_bulk(
            conversation_id,
            {"messages": assistant_messages},
        )
        updated_run = client.update_run(
            run["id"],
            {
                "strategy": result.strategy,
                "status": "completed",
                "result_summary": result.summary or "Run completed.",
            },
        )
        return ConversationExecuteResponse(
            run=RunRead.model_validate(updated_run),
            messages=[MessageRead.model_validate(message) for message in created_messages],
            workspace_path=result.workspace_path,
            artifact_dir=result.artifact_dir,
            strategy=result.strategy,
        )
    except HTTPException:
        raise
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        try:
            client = _server_client()
            run_id = locals().get("run", {}).get("id")
            if run_id:
                client.update_run(
                    run_id,
                    {
                        "strategy": "error",
                        "status": "failed",
                        "result_summary": str(exc),
                    },
                )
            if "conversation_id" in locals():
                client.create_message(
                    conversation_id,
                    {
                        "role": "assistant",
                        "agent": "jayai",
                        "content": f"Run failed\n{exc}",
                        "model_hint": "error",
                    },
                )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(exc)) from exc

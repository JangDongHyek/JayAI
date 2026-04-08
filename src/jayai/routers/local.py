from __future__ import annotations

import platform
import socket
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException

from ..schemas import (
    DeviceRead,
    ExecutionStartRequest,
    GitActionRead,
    GitActionRequest,
    LocalBootstrapResponse,
    LocalConfigRead,
    LocalConfigWrite,
    LocalJobRead,
    LocalProjectDetailRead,
    LocalStatusResponse,
    ProjectCreate,
    ProjectDetailRead,
    ProjectHandoffRead,
    ProjectHandoffUpsert,
    ProjectLoadRequest,
    ProjectRead,
    ProjectSaveRequest,
    ProjectSyncRead,
    ProjectUpdate,
    RunnerProbeRequest,
    RunnerProbeResponse,
    WorkspaceBindingRead,
    WorkspaceScanRequest,
    WorkspaceScanResponse,
)
from ..services.git_ops import clone_project, is_git_repo, pull_project, save_and_push_project, status_project
from ..services.job_manager import job_manager
from ..services.local_config import ensure_local_config, get_server_url, write_local_config
from ..services.runner import probe_local_environment, scan_workspace
from ..services.server_api import ServerApiError, ServerClient


router = APIRouter()


def _local_device_payload() -> dict[str, object]:
    config = ensure_local_config()
    return {
        "name": config["device_name"],
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "is_server": False,
    }


def _server_client() -> ServerClient:
    return ServerClient(get_server_url())


def _register_local_device(client: ServerClient) -> dict[str, object]:
    return client.register_device(_local_device_payload())


def _resolve_workspace_path(
    detail: ProjectDetailRead | dict[str, object],
    *,
    device_id: int,
    workspace_path: str | None,
) -> str:
    if workspace_path:
        return str(Path(workspace_path).expanduser().resolve())

    bindings = detail["bindings"] if isinstance(detail, dict) else detail.bindings
    own_binding = (
        next((item for item in bindings if item["device_id"] == device_id), None)
        if isinstance(detail, dict)
        else next((item for item in bindings if item.device_id == device_id), None)
    )
    if own_binding:
        return own_binding["local_path"] if isinstance(own_binding, dict) else own_binding.local_path
    raise HTTPException(status_code=400, detail="current device path is not configured yet")


def _active_binding_from_detail(detail: dict[str, object], device_id: int) -> WorkspaceBindingRead | None:
    for binding in detail["bindings"]:
        if binding["device_id"] == device_id:
            return WorkspaceBindingRead.model_validate(binding)
    return None


def _bind_current_device(
    client: ServerClient,
    *,
    project_id: int,
    device_id: int,
    local_path: str,
    default_branch: str,
) -> dict[str, object]:
    return client.bind_workspace(
        project_id,
        {
            "project_id": project_id,
            "device_id": device_id,
            "local_path": local_path,
            "preferred_branch": default_branch,
        },
    )


def _render_session_status(
    *,
    project: dict[str, object],
    workspace_path: str,
    device_name: str,
    project_brief: str,
    current_status: str,
    next_steps: str,
    notes: str,
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# {project['title']} Status",
        "",
        f"- Saved at: {timestamp}",
        f"- Device: {device_name}",
        f"- Project slug: {project['slug']}",
        f"- Repository: {project.get('repo_url') or '(none)'}",
        f"- Branch: {project.get('default_branch') or 'main'}",
        f"- Local path: {workspace_path}",
        "",
        "## Project Brief",
        project_brief.strip() or "(empty)",
        "",
        "## Current Status",
        current_status.strip() or "(empty)",
        "",
        "## Next Steps",
        next_steps.strip() or "(empty)",
        "",
        "## Notes",
        notes.strip() or "(empty)",
        "",
    ]
    return "\n".join(lines)


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local"}


@router.get("/api/local/config", response_model=LocalConfigRead)
def get_local_config() -> LocalConfigRead:
    return LocalConfigRead(**ensure_local_config())


@router.post("/api/local/config", response_model=LocalConfigRead)
def save_local_config(payload: LocalConfigWrite) -> LocalConfigRead:
    return LocalConfigRead(**write_local_config(device_name=payload.device_name))


@router.get("/api/local/status", response_model=LocalStatusResponse)
def local_status() -> LocalStatusResponse:
    config = ensure_local_config()
    server_url = config["server_url"]
    server_reachable = False
    try:
        server_reachable = ServerClient(server_url).health().get("status") == "ok"
    except ServerApiError:
        server_reachable = False
    return LocalStatusResponse(
        server_url=server_url,
        server_reachable=server_reachable,
        local_device_name=config["device_name"],
        local_hostname=socket.gethostname(),
        local_platform=platform.platform(),
    )


@router.get("/api/local/bootstrap", response_model=LocalBootstrapResponse)
def bootstrap() -> LocalBootstrapResponse:
    config = ensure_local_config()
    server_url = config["server_url"]
    base_payload = {
        "server_url": server_url,
        "local_device_name": config["device_name"],
        "local_hostname": socket.gethostname(),
        "local_platform": platform.platform(),
    }
    try:
        client = ServerClient(server_url)
        server_reachable = client.health().get("status") == "ok"
        device = _register_local_device(client)
        projects = client.list_projects()
    except (RuntimeError, ServerApiError):
        return LocalBootstrapResponse(server_reachable=False, **base_payload)

    return LocalBootstrapResponse(
        server_reachable=server_reachable,
        **base_payload,
        device=DeviceRead.model_validate(device),
        projects=[ProjectRead.model_validate(item) for item in projects],
    )


@router.post("/api/runner/probe", response_model=RunnerProbeResponse)
def probe_runner(payload: RunnerProbeRequest) -> RunnerProbeResponse:
    return probe_local_environment(payload.workdir)


@router.post("/api/runner/scan-workspace", response_model=WorkspaceScanResponse)
def scan_runner_workspace(payload: WorkspaceScanRequest) -> WorkspaceScanResponse:
    return scan_workspace(payload.path)


@router.post("/api/local/projects", response_model=ProjectRead)
def create_project(payload: ProjectCreate) -> ProjectRead:
    try:
        project = _server_client().create_project(payload.model_dump())
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProjectRead.model_validate(project)


@router.patch("/api/local/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, payload: ProjectUpdate) -> ProjectRead:
    try:
        project = _server_client().update_project(project_id, payload.model_dump(exclude_unset=True))
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProjectRead.model_validate(project)


@router.get("/api/local/projects/{project_id}", response_model=LocalProjectDetailRead)
def get_local_project_detail(project_id: int) -> LocalProjectDetailRead:
    try:
        client = _server_client()
        device = _register_local_device(client)
        detail = client.get_project_detail(project_id)
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return LocalProjectDetailRead(
        project=ProjectRead.model_validate(detail["project"]),
        bindings=[WorkspaceBindingRead.model_validate(item) for item in detail["bindings"]],
        active_binding=_active_binding_from_detail(detail, device["id"]),
        handoff=ProjectHandoffRead.model_validate(detail["handoff"]),
    )


@router.post("/api/local/projects/{project_id}/binding", response_model=WorkspaceBindingRead)
def save_binding(project_id: int, payload: GitActionRequest) -> WorkspaceBindingRead:
    workspace_path = payload.workspace_path
    if not workspace_path:
        raise HTTPException(status_code=400, detail="workspace path is empty")
    resolved = str(Path(workspace_path).expanduser().resolve())
    try:
        client = _server_client()
        device = _register_local_device(client)
        project = client.get_project(project_id)
        binding = client.bind_workspace(
            project_id,
            {
                "project_id": project_id,
                "device_id": device["id"],
                "local_path": resolved,
                "preferred_branch": project["default_branch"],
            },
        )
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkspaceBindingRead.model_validate(binding)


@router.post("/api/local/projects/{project_id}/load", response_model=ProjectSyncRead)
def load_project(project_id: int, payload: ProjectLoadRequest) -> ProjectSyncRead:
    try:
        client = _server_client()
        device = _register_local_device(client)
        detail = client.get_project_detail(project_id)
        project = detail["project"]
        workspace_path = _resolve_workspace_path(
            detail,
            device_id=device["id"],
            workspace_path=payload.workspace_path,
        )
        path_obj = Path(workspace_path)

        if path_obj.exists() and is_git_repo(path_obj):
            result = pull_project(path_obj, project["default_branch"])
        else:
            if not project.get("repo_url"):
                raise HTTPException(status_code=400, detail="repo URL is missing")
            result = clone_project(project["repo_url"], path_obj, project["default_branch"])

        _bind_current_device(
            client,
            project_id=project_id,
            device_id=device["id"],
            local_path=str(path_obj),
            default_branch=project["default_branch"],
        )
    except HTTPException:
        raise
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    output = "\n\n".join(part for part in [result.summary, result.stdout, result.stderr] if part)
    return ProjectSyncRead(
        action="load",
        success=result.success,
        summary=result.summary,
        output=output,
        workspace_path=str(path_obj),
        file_path=None,
        command=result.command,
    )


@router.put("/api/local/projects/{project_id}/handoff", response_model=ProjectHandoffRead)
def save_handoff(project_id: int, payload: ProjectHandoffUpsert) -> ProjectHandoffRead:
    try:
        handoff = _server_client().save_handoff(project_id, payload.model_dump())
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProjectHandoffRead.model_validate(handoff)


@router.post("/api/local/projects/{project_id}/save", response_model=ProjectSyncRead)
def save_project(project_id: int, payload: ProjectSaveRequest) -> ProjectSyncRead:
    try:
        client = _server_client()
        device = _register_local_device(client)
        detail = client.get_project_detail(project_id)
        project = detail["project"]
        workspace_path = _resolve_workspace_path(
            detail,
            device_id=device["id"],
            workspace_path=payload.workspace_path,
        )
        path_obj = Path(workspace_path)
        if not path_obj.exists() or not path_obj.is_dir():
            raise HTTPException(status_code=400, detail="workspace path does not exist")

        handoff_payload = {
            "project_brief": payload.project_brief.strip(),
            "current_status": payload.current_status.strip(),
            "next_steps": payload.next_steps.strip(),
            "notes": payload.notes.strip(),
            "updated_by_device": device["name"],
        }
        client.save_handoff(project_id, handoff_payload)
        _bind_current_device(
            client,
            project_id=project_id,
            device_id=device["id"],
            local_path=str(path_obj),
            default_branch=project["default_branch"],
        )

        status_file = path_obj / "SESSION_STATUS.md"
        status_file.write_text(
            _render_session_status(
                project=project,
                workspace_path=str(path_obj),
                device_name=device["name"],
                project_brief=handoff_payload["project_brief"],
                current_status=handoff_payload["current_status"],
                next_steps=handoff_payload["next_steps"],
                notes=handoff_payload["notes"],
            ),
            encoding="utf-8",
        )

        git_result = save_and_push_project(
            path_obj,
            payload.commit_message or "chore: save progress",
        )
    except HTTPException:
        raise
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    output = "\n\n".join(
        part
        for part in [
            f"Status file: {status_file}",
            git_result.summary,
            git_result.stdout,
            git_result.stderr,
        ]
        if part
    )
    return ProjectSyncRead(
        action="save",
        success=git_result.success,
        summary=git_result.summary,
        output=output,
        workspace_path=str(path_obj),
        file_path=str(status_file),
        command=git_result.command,
    )


@router.post("/api/local/projects/{project_id}/git/{action}", response_model=GitActionRead)
def run_git_action(project_id: int, action: str, payload: GitActionRequest) -> GitActionRead:
    if action not in {"clone", "pull", "status"}:
        raise HTTPException(status_code=404, detail="unsupported git action")

    try:
        client = _server_client()
        device = _register_local_device(client)
        detail = client.get_project_detail(project_id)
        workspace_path = _resolve_workspace_path(detail, device_id=device["id"], workspace_path=payload.workspace_path)
        project = detail["project"]
        path_obj = Path(workspace_path)

        if action == "clone":
            if not project.get("repo_url"):
                raise HTTPException(status_code=400, detail="repo URL is missing")
            result = clone_project(project["repo_url"], path_obj, project["default_branch"])
        elif action == "pull":
            result = pull_project(path_obj, project["default_branch"])
        else:
            result = status_project(path_obj)
    except HTTPException:
        raise
    except (RuntimeError, ServerApiError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GitActionRead(
        action=result.action,
        success=result.success,
        summary=result.summary,
        stdout=result.stdout,
        stderr=result.stderr,
        command=result.command,
        workspace_path=str(path_obj),
    )


@router.post("/api/local/projects/{project_id}/jobs", response_model=LocalJobRead)
def start_execution(project_id: int, payload: ExecutionStartRequest) -> LocalJobRead:
    try:
        client = _server_client()
        device = _register_local_device(client)
        detail = client.get_project_detail(project_id)
        workspace_path = _resolve_workspace_path(detail, device_id=device["id"], workspace_path=payload.workspace_path)
        handoff = detail["handoff"]
        handoff_text = "\n\n".join(
            part
            for part in [
                f"[Project Brief]\n{handoff['project_brief']}" if handoff.get("project_brief") else "",
                f"[Current Status]\n{handoff['current_status']}" if handoff.get("current_status") else "",
                f"[Next Steps]\n{handoff['next_steps']}" if handoff.get("next_steps") else "",
                f"[Notes]\n{handoff['notes']}" if handoff.get("notes") else "",
            ]
            if part
        ).strip()
        project = SimpleNamespace(**detail["project"])
        return job_manager.start_execution(
            project=project,
            workspace_path=workspace_path,
            prompt=payload.prompt,
            handoff_text=handoff_text,
            mode=payload.mode,
        )
    except HTTPException:
        raise
    except ServerApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/api/local/jobs/active", response_model=LocalJobRead | None)
def get_active_job() -> LocalJobRead | None:
    return job_manager.active()


@router.get("/api/local/jobs/{job_id}", response_model=LocalJobRead)
def get_job(job_id: str) -> LocalJobRead:
    try:
        return job_manager.get(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

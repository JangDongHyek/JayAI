from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


DEFAULT_DOCS_GLOBS = [
    "AGENTS.md",
    "README.md",
    "README*.md",
    "CLAUDE.md",
    "SESSION_STATUS.md",
    "docs/**/*.md",
]


class ProjectCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    repo_url: str | None = None
    default_branch: str = "main"
    docs_globs: list[str] = Field(default_factory=lambda: list(DEFAULT_DOCS_GLOBS))


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    repo_url: str | None = None
    default_branch: str | None = Field(default=None, min_length=1, max_length=120)
    docs_globs: list[str] | None = None


class ProjectRead(ORMModel):
    id: int
    slug: str
    title: str
    repo_url: str | None
    default_branch: str
    docs_globs: list[str]
    created_at: datetime
    updated_at: datetime


class DeviceRegister(BaseModel):
    name: str
    hostname: str
    platform: str
    is_server: bool = False


class DeviceRead(ORMModel):
    id: int
    name: str
    hostname: str
    platform: str
    is_server: bool
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class WorkspaceBindingCreate(BaseModel):
    project_id: int
    device_id: int
    local_path: str
    preferred_branch: str | None = None


class WorkspaceBindingRead(ORMModel):
    id: int
    project_id: int
    device_id: int
    local_path: str
    preferred_branch: str | None
    created_at: datetime
    updated_at: datetime


class ProjectHandoffUpsert(BaseModel):
    project_brief: str = ""
    current_status: str = ""
    next_steps: str = ""
    notes: str = ""
    updated_by_device: str | None = None


class ProjectHandoffRead(ORMModel):
    id: int | None = None
    project_id: int
    project_brief: str = ""
    current_status: str = ""
    next_steps: str = ""
    notes: str = ""
    updated_by_device: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectDetailRead(BaseModel):
    project: ProjectRead
    bindings: list[WorkspaceBindingRead]
    handoff: ProjectHandoffRead


class LocalConfigRead(BaseModel):
    server_url: str


class LocalConfigWrite(BaseModel):
    server_url: str = Field(min_length=1)


class LocalStatusResponse(BaseModel):
    server_url: str
    server_reachable: bool
    local_device_name: str
    local_hostname: str
    local_platform: str


class ToolStatus(BaseModel):
    name: str
    installed: bool
    executable: str | None = None
    version: str | None = None
    auth_state: str | None = None
    detail: str | None = None


class RunnerProbeRequest(BaseModel):
    workdir: str | None = None


class RunnerProbeResponse(BaseModel):
    hostname: str
    platform: str
    cwd: str
    tools: list[ToolStatus]


class WorkspaceScanRequest(BaseModel):
    path: str


class WorkspaceScanResponse(BaseModel):
    path: str
    exists: bool
    is_git_repo: bool
    top_entries: list[str]
    context_docs: list[str]


class LocalBootstrapResponse(BaseModel):
    server_url: str
    server_reachable: bool
    device: DeviceRead | None = None
    projects: list[ProjectRead] = Field(default_factory=list)


class LocalProjectDetailRead(BaseModel):
    project: ProjectRead
    bindings: list[WorkspaceBindingRead]
    active_binding: WorkspaceBindingRead | None = None
    handoff: ProjectHandoffRead


class GitActionRequest(BaseModel):
    workspace_path: str | None = None


class GitActionRead(BaseModel):
    action: str
    success: bool
    summary: str
    stdout: str
    stderr: str
    command: list[str]
    workspace_path: str


class ProjectLoadRequest(BaseModel):
    workspace_path: str | None = None


class ProjectSaveRequest(BaseModel):
    workspace_path: str | None = None
    project_brief: str = ""
    current_status: str = ""
    next_steps: str = ""
    notes: str = ""
    commit_message: str | None = None


class ProjectSyncRead(BaseModel):
    action: str
    success: bool
    summary: str
    output: str
    workspace_path: str
    file_path: str | None = None
    command: list[str] = Field(default_factory=list)


class ExecutionStartRequest(BaseModel):
    prompt: str = Field(min_length=1)
    mode: Literal["codex", "claude", "both"] = "both"
    workspace_path: str | None = None


class LocalJobRead(BaseModel):
    id: str
    project_id: int
    kind: str
    mode: str | None = None
    status: Literal["queued", "running", "completed", "failed"]
    phase: str
    prompt: str | None = None
    output: str = ""
    error: str | None = None
    workspace_path: str | None = None
    artifact_dir: str | None = None
    started_at: datetime
    finished_at: datetime | None = None

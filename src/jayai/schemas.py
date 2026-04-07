from __future__ import annotations

from datetime import datetime

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


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationRead(ORMModel):
    id: int
    project_id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    role: str
    agent: str | None = None
    content: str
    model_hint: str | None = None


class MessageRead(ORMModel):
    id: int
    conversation_id: int
    role: str
    agent: str | None
    content: str
    model_hint: str | None
    created_at: datetime
    updated_at: datetime


class MessageBatchCreate(BaseModel):
    messages: list[MessageCreate] = Field(min_length=1)


class RunRead(ORMModel):
    id: int
    conversation_id: int
    device_id: int | None
    strategy: str
    status: str
    prompt_excerpt: str | None
    result_summary: str | None
    created_at: datetime
    updated_at: datetime


class RunCreate(BaseModel):
    device_id: int | None = None
    strategy: str
    status: str = "running"
    prompt_excerpt: str | None = None
    result_summary: str | None = None


class RunUpdate(BaseModel):
    strategy: str | None = None
    status: str | None = None
    result_summary: str | None = None


class ConversationExecuteRequest(BaseModel):
    content: str = Field(min_length=1)
    workspace_path: str | None = None


class ConversationExecuteResponse(BaseModel):
    run: RunRead
    messages: list[MessageRead]
    workspace_path: str
    artifact_dir: str | None = None
    strategy: str


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


class RunnerProbeRequest(BaseModel):
    workdir: str | None = None


class ToolStatus(BaseModel):
    name: str
    installed: bool
    executable: str | None = None
    version: str | None = None
    auth_state: str | None = None
    detail: str | None = None


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

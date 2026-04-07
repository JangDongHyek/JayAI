from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
from pathlib import Path

from ..schemas import RunnerProbeResponse, ToolStatus, WorkspaceScanResponse


WINDOWS_CODEX_CANDIDATES = [
    Path.home() / "AppData" / "Roaming" / "npm" / "codex.cmd",
    Path.home() / "AppData" / "Roaming" / "npm" / "codex",
]
WINDOWS_CLAUDE_CANDIDATES = [
    Path.home() / "AppData" / "Roaming" / "npm" / "claude.cmd",
    Path.home() / "AppData" / "Roaming" / "npm" / "claude",
]


def _find_executable(name: str, candidates: list[Path] | None = None) -> str | None:
    found = shutil.which(name)
    if found and "WindowsApps" not in found:
        return found
    for candidate in candidates or []:
        if candidate.exists():
            return str(candidate)
    if found:
        return found
    return None


def _run_command(command: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        return completed.returncode, (completed.stdout or "").strip(), (completed.stderr or "").strip()
    except OSError as exc:
        return 1, "", str(exc)


def _probe_codex() -> ToolStatus:
    executable = _find_executable("codex", WINDOWS_CODEX_CANDIDATES)
    if not executable:
        return ToolStatus(name="codex", installed=False, detail="not found")
    version_code, version_out, version_err = _run_command([executable, "--version"])
    auth_code, auth_out, auth_err = _run_command([executable, "login", "status"])
    auth_state = auth_out or auth_err or ("logged in" if auth_code == 0 else "not logged in")
    return ToolStatus(
        name="codex",
        installed=True,
        executable=executable,
        version=version_out if version_code == 0 else None,
        auth_state=auth_state,
        detail=version_err or None,
    )


def _probe_claude() -> ToolStatus:
    executable = _find_executable("claude", WINDOWS_CLAUDE_CANDIDATES)
    if not executable:
        return ToolStatus(name="claude", installed=False, detail="not found")
    version_code, version_out, version_err = _run_command([executable, "--version"])
    auth_code, auth_out, auth_err = _run_command([executable, "auth", "status"])
    auth_state = "unknown"
    if auth_code == 0 and auth_out:
        try:
            payload = json.loads(auth_out)
            auth_state = "logged in" if payload.get("loggedIn") else "not logged in"
        except json.JSONDecodeError:
            auth_state = auth_out
    elif auth_err:
        auth_state = auth_err
    return ToolStatus(
        name="claude",
        installed=True,
        executable=executable,
        version=version_out if version_code == 0 else None,
        auth_state=auth_state,
        detail=version_err or None,
    )


def _probe_basic_tool(name: str) -> ToolStatus:
    executable = _find_executable(name)
    if not executable:
        return ToolStatus(name=name, installed=False, detail="not found")
    version_arg = "--version"
    if name == "node":
        version_arg = "-v"
    code, out, err = _run_command([executable, version_arg])
    return ToolStatus(
        name=name,
        installed=True,
        executable=executable,
        version=out if code == 0 else None,
        detail=err or None,
    )


def probe_local_environment(workdir: str | None = None) -> RunnerProbeResponse:
    cwd = Path(workdir).resolve() if workdir else Path.cwd().resolve()
    tools = [
        _probe_codex(),
        _probe_claude(),
        _probe_basic_tool("git"),
        _probe_basic_tool("node"),
        _probe_basic_tool("python"),
    ]
    return RunnerProbeResponse(
        hostname=socket.gethostname(),
        platform=platform.platform(),
        cwd=str(cwd),
        tools=tools,
    )


def scan_workspace(path_value: str) -> WorkspaceScanResponse:
    path = Path(path_value).expanduser().resolve()
    exists = path.exists()
    is_git_repo = False
    top_entries: list[str] = []
    context_docs: list[str] = []

    if exists and path.is_dir():
        try:
            top_entries = sorted(item.name for item in path.iterdir())[:20]
        except PermissionError:
            top_entries = ["[permission denied]"]
        try:
            git_code, git_out, _ = _run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
            is_git_repo = git_code == 0 and git_out == "true"
        except OSError:
            is_git_repo = False
        for pattern in ("AGENTS.md", "README.md", "CLAUDE.md", "docs/**/*.md"):
            for matched in path.glob(pattern):
                if matched.is_file():
                    context_docs.append(str(matched.relative_to(path)))
        context_docs = sorted(set(context_docs))

    return WorkspaceScanResponse(
        path=str(path),
        exists=exists,
        is_git_repo=is_git_repo,
        top_entries=top_entries,
        context_docs=context_docs,
    )

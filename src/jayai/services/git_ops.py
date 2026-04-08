from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitActionResult:
    action: str
    success: bool
    summary: str
    stdout: str
    stderr: str
    command: list[str]


def is_git_repo(path: Path) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and (completed.stdout or "").strip() == "true"


def _run_git(command: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return completed.returncode, (completed.stdout or "").strip(), (completed.stderr or "").strip()


def clone_project(repo_url: str, workspace_path: Path, default_branch: str) -> GitActionResult:
    if workspace_path.exists():
        if workspace_path.is_dir() and is_git_repo(workspace_path):
            return pull_project(workspace_path, default_branch, fallback_action="clone")
        if workspace_path.is_dir() and any(workspace_path.iterdir()):
            return GitActionResult(
                action="clone",
                success=False,
                summary=f"git clone 중단. 대상 경로가 비어 있지 않음: {workspace_path}",
                stdout="",
                stderr="target directory is not empty",
                command=["git", "clone", repo_url, str(workspace_path)],
            )

    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    command = ["git", "clone", "--branch", default_branch, repo_url, str(workspace_path)]
    code, stdout, stderr = _run_git(command)
    summary = f"git clone {'성공' if code == 0 else '실패'}: {workspace_path}"
    return GitActionResult(
        action="clone",
        success=code == 0,
        summary=summary,
        stdout=stdout,
        stderr=stderr,
        command=command,
    )


def pull_project(workspace_path: Path, default_branch: str, fallback_action: str = "pull") -> GitActionResult:
    if not workspace_path.exists() or not workspace_path.is_dir():
        return GitActionResult(
            action=fallback_action,
            success=False,
            summary=f"git pull 불가. 경로 없음: {workspace_path}",
            stdout="",
            stderr="workspace path does not exist",
            command=["git", "pull", "--ff-only", "origin", default_branch],
        )
    if not is_git_repo(workspace_path):
        return GitActionResult(
            action=fallback_action,
            success=False,
            summary=f"git pull 불가. git 저장소 아님: {workspace_path}",
            stdout="",
            stderr="not a git repository",
            command=["git", "pull", "--ff-only", "origin", default_branch],
        )

    command = ["git", "pull", "--ff-only", "origin", default_branch]
    code, stdout, stderr = _run_git(command, cwd=workspace_path)
    summary = f"git pull {'성공' if code == 0 else '실패'}: {workspace_path}"
    return GitActionResult(
        action=fallback_action,
        success=code == 0,
        summary=summary,
        stdout=stdout,
        stderr=stderr,
        command=command,
    )


def status_project(workspace_path: Path) -> GitActionResult:
    if not workspace_path.exists() or not workspace_path.is_dir():
        return GitActionResult(
            action="status",
            success=False,
            summary=f"git status 불가. 경로 없음: {workspace_path}",
            stdout="",
            stderr="workspace path does not exist",
            command=["git", "status", "--short", "--branch"],
        )
    if not is_git_repo(workspace_path):
        return GitActionResult(
            action="status",
            success=False,
            summary=f"git status 불가. git 저장소 아님: {workspace_path}",
            stdout="",
            stderr="not a git repository",
            command=["git", "status", "--short", "--branch"],
        )

    command = ["git", "status", "--short", "--branch"]
    code, stdout, stderr = _run_git(command, cwd=workspace_path)
    summary = f"git status {'성공' if code == 0 else '실패'}: {workspace_path}"
    return GitActionResult(
        action="status",
        success=code == 0,
        summary=summary,
        stdout=stdout,
        stderr=stderr,
        command=command,
    )

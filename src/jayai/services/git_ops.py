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


def _failure(action: str, workspace_path: Path, stderr: str, command: list[str]) -> GitActionResult:
    return GitActionResult(
        action=action,
        success=False,
        summary=f"{action} failed: {workspace_path}",
        stdout="",
        stderr=stderr,
        command=command,
    )


def _run_git(command: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return completed.returncode, (completed.stdout or "").strip(), (completed.stderr or "").strip()


def is_git_repo(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and (completed.stdout or "").strip() == "true"


def current_branch(workspace_path: Path, fallback: str = "main") -> str:
    code, stdout, _ = _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=workspace_path)
    if code == 0 and stdout:
        return stdout
    return fallback


def save_and_push_project(workspace_path: Path, commit_message: str) -> GitActionResult:
    if not workspace_path.exists() or not workspace_path.is_dir():
        return _failure("save", workspace_path, "workspace path does not exist", ["git", "add", "-A"])
    if not is_git_repo(workspace_path):
        return _failure("save", workspace_path, "not a git repository", ["git", "add", "-A"])

    steps: list[str] = []

    add_command = ["git", "add", "-A"]
    add_code, add_stdout, add_stderr = _run_git(add_command, cwd=workspace_path)
    if add_code != 0:
        return GitActionResult(
            action="save",
            success=False,
            summary=f"save failed: {workspace_path}",
            stdout=add_stdout,
            stderr=add_stderr,
            command=add_command,
        )
    steps.append("[git add -A]")

    diff_code, _, _ = _run_git(["git", "diff", "--cached", "--quiet"], cwd=workspace_path)
    commit_output_parts: list[str] = []

    if diff_code == 1:
        commit_command = ["git", "commit", "-m", commit_message]
        commit_code, commit_stdout, commit_stderr = _run_git(commit_command, cwd=workspace_path)
        commit_output_parts.extend(part for part in [commit_stdout, commit_stderr] if part)
        if commit_code != 0:
            return GitActionResult(
                action="save",
                success=False,
                summary=f"commit failed: {workspace_path}",
                stdout="\n\n".join(commit_output_parts),
                stderr=commit_stderr,
                command=commit_command,
            )
        steps.append("[git commit]")
    else:
        steps.append("[commit skipped: no staged changes]")

    branch = current_branch(workspace_path)
    push_command = ["git", "push", "origin", branch]
    push_code, push_stdout, push_stderr = _run_git(push_command, cwd=workspace_path)
    output = "\n\n".join(
        part
        for part in [
            "\n".join(steps),
            *commit_output_parts,
            push_stdout,
            push_stderr,
        ]
        if part
    )
    return GitActionResult(
        action="save",
        success=push_code == 0,
        summary=f"save {'succeeded' if push_code == 0 else 'failed'}: {workspace_path}",
        stdout=output,
        stderr="" if push_code == 0 else push_stderr,
        command=push_command,
    )


def clone_project(repo_url: str, workspace_path: Path, default_branch: str) -> GitActionResult:
    if workspace_path.exists():
        if workspace_path.is_dir() and is_git_repo(workspace_path):
            return pull_project(workspace_path, default_branch, fallback_action="clone")
        if workspace_path.is_dir() and any(workspace_path.iterdir()):
            return GitActionResult(
                action="clone",
                success=False,
                summary=f"git clone stopped because target is not empty: {workspace_path}",
                stdout="",
                stderr="target directory is not empty",
                command=["git", "clone", repo_url, str(workspace_path)],
            )

    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    command = ["git", "clone", "--branch", default_branch, repo_url, str(workspace_path)]
    code, stdout, stderr = _run_git(command)
    return GitActionResult(
        action="clone",
        success=code == 0,
        summary=f"git clone {'succeeded' if code == 0 else 'failed'}: {workspace_path}",
        stdout=stdout,
        stderr=stderr,
        command=command,
    )


def pull_project(workspace_path: Path, default_branch: str, fallback_action: str = "pull") -> GitActionResult:
    if not workspace_path.exists() or not workspace_path.is_dir():
        return GitActionResult(
            action=fallback_action,
            success=False,
            summary=f"git pull unavailable because path does not exist: {workspace_path}",
            stdout="",
            stderr="workspace path does not exist",
            command=["git", "pull", "--ff-only", "origin", default_branch],
        )
    if not is_git_repo(workspace_path):
        return GitActionResult(
            action=fallback_action,
            success=False,
            summary=f"git pull unavailable because path is not a repo: {workspace_path}",
            stdout="",
            stderr="not a git repository",
            command=["git", "pull", "--ff-only", "origin", default_branch],
        )

    command = ["git", "pull", "--ff-only", "origin", default_branch]
    code, stdout, stderr = _run_git(command, cwd=workspace_path)
    return GitActionResult(
        action=fallback_action,
        success=code == 0,
        summary=f"git pull {'succeeded' if code == 0 else 'failed'}: {workspace_path}",
        stdout=stdout,
        stderr=stderr,
        command=command,
    )


def status_project(workspace_path: Path) -> GitActionResult:
    if not workspace_path.exists() or not workspace_path.is_dir():
        return GitActionResult(
            action="status",
            success=False,
            summary=f"git status unavailable because path does not exist: {workspace_path}",
            stdout="",
            stderr="workspace path does not exist",
            command=["git", "status", "--short", "--branch"],
        )
    if not is_git_repo(workspace_path):
        return GitActionResult(
            action="status",
            success=False,
            summary=f"git status unavailable because path is not a repo: {workspace_path}",
            stdout="",
            stderr="not a git repository",
            command=["git", "status", "--short", "--branch"],
        )

    command = ["git", "status", "--short", "--branch"]
    code, stdout, stderr = _run_git(command, cwd=workspace_path)
    return GitActionResult(
        action="status",
        success=code == 0,
        summary=f"git status {'succeeded' if code == 0 else 'failed'}: {workspace_path}",
        stdout=stdout,
        stderr=stderr,
        command=command,
    )

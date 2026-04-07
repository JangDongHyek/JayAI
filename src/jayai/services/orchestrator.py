from __future__ import annotations

import json
import locale
import os
import shutil
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from ..config import get_settings
from ..models import Project
from .git_ops import GitActionResult, clone_project, detect_git_action, pull_project, status_project
from .project_context import (
    ContextFile,
    ProjectProfile,
    build_claude_context_block,
    build_claude_prompt,
    build_codex_prompt,
    collect_context_files,
    extract_section,
    load_project_profile,
    render_context_packet,
    render_tree,
    resolve_strategy,
)


settings = get_settings()
WINDOWS_CLAUDE_CANDIDATES = [
    Path.home() / "AppData" / "Roaming" / "npm" / "claude.cmd",
    Path.home() / "AppData" / "Roaming" / "npm" / "claude",
]
WINDOWS_CODEX_CANDIDATES = [
    Path.home() / "AppData" / "Roaming" / "npm" / "codex.cmd",
    Path.home() / "AppData" / "Roaming" / "npm" / "codex",
]
WINDOWS_GIT_BASH_CANDIDATES = [
    Path(r"C:\Program Files\Git\bin\bash.exe"),
    Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
]


@dataclass
class AgentResult:
    name: str
    command: list[str]
    returncode: int
    duration_sec: float
    output: str
    stdout: str
    stderr: str
    output_path: str
    stdout_path: str
    stderr_path: str
    success: bool
    final: str
    critique: str
    follow_up: str
    project_context: str
    handoff: str


@dataclass
class ExecutionResult:
    mode: str
    strategy: str
    workspace_path: str
    artifact_dir: str | None
    summary: str
    codex: AgentResult | None
    claude: AgentResult | None
    git: GitActionResult | None


def _first_existing(paths: Sequence[Path]) -> str | None:
    for path in paths:
        if path.exists():
            return str(path)
    return None


def _detect_cmd(primary: str, windows_candidates: Sequence[Path]) -> str:
    found = shutil.which(f"{primary}.cmd") or shutil.which(primary)
    if found and "WindowsApps" not in found:
        return found
    candidate = _first_existing(windows_candidates)
    if candidate:
        return candidate
    if found:
        return found
    raise RuntimeError(f"{primary} executable not found")


def _detect_git_bash() -> str | None:
    env_value = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if env_value and Path(env_value).exists():
        return env_value
    return _first_existing(WINDOWS_GIT_BASH_CANDIDATES)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _decode_output(payload: bytes | None) -> str:
    data = payload or b""
    for encoding in ("utf-8", locale.getpreferredencoding(False), "cp949"):
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _is_git_repo(path: Path) -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0 and (probe.stdout or "").strip() == "true"


def _build_codex_command(codex_cmd: str, output_path: Path, sandbox: str, workdir: Path) -> list[str]:
    command = [codex_cmd, "exec", "-s", sandbox, "-o", str(output_path)]
    if not _is_git_repo(workdir):
        command.append("--skip-git-repo-check")
    return command


def _build_claude_command(claude_cmd: str) -> list[str]:
    return [claude_cmd, "-p", "--permission-mode", "acceptEdits"]


def _run_process(
    *,
    name: str,
    command: list[str],
    stdin_text: str,
    cwd: Path,
    env: dict[str, str],
    timeout_sec: int,
    output_path: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> AgentResult:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            input=stdin_text.encode("utf-8"),
            cwd=cwd,
            env=env,
            capture_output=True,
            text=False,
            timeout=timeout_sec,
        )
        duration = time.perf_counter() - started
        stdout = _decode_output(completed.stdout)
        stderr = _decode_output(completed.stderr)
        _write_text(stdout_path, stdout)
        _write_text(stderr_path, stderr)
        output = output_path.read_text(encoding="utf-8") if output_path.exists() else stdout
        if not output_path.exists():
            _write_text(output_path, output)
        return _build_agent_result(
            name=name,
            command=command,
            returncode=completed.returncode,
            duration_sec=duration,
            output=output,
            stdout=stdout,
            stderr=stderr,
            output_path=output_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - started
        stdout = _decode_output(exc.stdout)
        stderr = _decode_output(exc.stderr)
        timeout_note = f"{name} timed out after {timeout_sec} seconds."
        _write_text(stdout_path, stdout)
        _write_text(stderr_path, stderr + ("\n" if stderr else "") + timeout_note)
        _write_text(output_path, timeout_note)
        return _build_agent_result(
            name=name,
            command=command,
            returncode=124,
            duration_sec=duration,
            output=timeout_note,
            stdout=stdout,
            stderr=stderr + ("\n" if stderr else "") + timeout_note,
            output_path=output_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )


def _build_agent_result(
    *,
    name: str,
    command: list[str],
    returncode: int,
    duration_sec: float,
    output: str,
    stdout: str,
    stderr: str,
    output_path: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> AgentResult:
    return AgentResult(
        name=name,
        command=command,
        returncode=returncode,
        duration_sec=duration_sec,
        output=output,
        stdout=stdout,
        stderr=stderr,
        output_path=str(output_path),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        success=returncode == 0,
        final=extract_section(output, "FINAL"),
        critique=extract_section(output, "CRITIQUE"),
        follow_up=extract_section(output, "FOLLOW_UP"),
        project_context=extract_section(output, "PROJECT_CONTEXT"),
        handoff=extract_section(output, "HANDOFF_FOR_CLAUDE"),
    )


def _run_parallel_tasks(
    tasks: list[tuple[str, list[str], str, Path, Path, Path]],
    cwd: Path,
    env: dict[str, str],
    timeout_sec: int,
) -> dict[str, AgentResult]:
    results: dict[str, AgentResult] = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_map = {
            executor.submit(
                _run_process,
                name=name,
                command=command,
                stdin_text=stdin_text,
                cwd=cwd,
                env=env,
                timeout_sec=timeout_sec,
                output_path=output_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            ): name
            for name, command, stdin_text, output_path, stdout_path, stderr_path in tasks
        }
        for future in as_completed(future_map):
            result = future.result()
            results[result.name] = result
    return results


def _compose_summary(codex: AgentResult, claude: AgentResult) -> str:
    chunks: list[str] = []
    if codex.final:
        chunks.append(f"[Codex]\n{codex.final}")
    if claude.final:
        chunks.append(f"[Claude]\n{claude.final}")
    if claude.critique:
        chunks.append(f"[검토]\n{claude.critique}")
    if claude.follow_up:
        chunks.append(f"[다음]\n{claude.follow_up}")
    return "\n\n".join(chunk for chunk in chunks if chunk).strip()


def _render_meta(
    *,
    prompt: str,
    workdir: Path,
    strategy: str,
    profile: ProjectProfile,
    config_path: Path | None,
    context_files: list[ContextFile],
    codex: AgentResult,
    claude: AgentResult,
) -> str:
    payload = {
        "prompt": prompt,
        "workdir": str(workdir),
        "strategy": strategy,
        "project_name": profile.project_name,
        "config_path": str(config_path) if config_path else "",
        "hostname": socket.gethostname(),
        "context_files": [asdict(item) for item in context_files],
        "codex": asdict(codex),
        "claude": asdict(claude),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _maybe_handle_git_task(project: Project, prompt: str, workspace_path: Path) -> GitActionResult | None:
    action = detect_git_action(prompt)
    if not action:
        return None
    if action == "clone":
        if not project.repo_url:
            return GitActionResult(
                action="clone",
                success=False,
                summary="git clone 불가. 프로젝트 repo_url 없음.",
                stdout="",
                stderr="repo_url missing",
                command=[],
            )
        return clone_project(project.repo_url, workspace_path, project.default_branch)
    if action == "pull":
        return pull_project(workspace_path, project.default_branch)
    return status_project(workspace_path)


def execute_user_task(
    *,
    project: Project,
    workspace_path: str,
    prompt: str,
    timeout_sec: int = 900,
    codex_sandbox: str = "workspace-write",
) -> ExecutionResult:
    workdir = Path(workspace_path).expanduser().resolve()
    git_result = _maybe_handle_git_task(project, prompt, workdir)
    if git_result:
        return ExecutionResult(
            mode="git",
            strategy="git",
            workspace_path=str(workdir),
            artifact_dir=None,
            summary="\n".join(part for part in [git_result.summary, git_result.stdout, git_result.stderr] if part).strip(),
            codex=None,
            claude=None,
            git=git_result,
        )

    if not workdir.exists() or not workdir.is_dir():
        raise RuntimeError(f"workspace path not found: {workdir}")

    profile, config_path, _ = load_project_profile(workdir, docs_globs=project.docs_globs)
    context_files = collect_context_files(workdir, profile)
    tree_text = render_tree(workdir, profile)
    context_packet = render_context_packet(profile, config_path, context_files, tree_text)
    strategy = resolve_strategy(profile, has_context=bool(context_files))

    codex_cmd = _detect_cmd("codex", WINDOWS_CODEX_CANDIDATES)
    claude_cmd = _detect_cmd("claude", WINDOWS_CLAUDE_CANDIDATES)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = settings.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    codex_output_path = run_dir / "codex.txt"
    claude_output_path = run_dir / "claude.txt"
    codex_stdout_path = run_dir / "codex.stdout.txt"
    codex_stderr_path = run_dir / "codex.stderr.txt"
    claude_stdout_path = run_dir / "claude.stdout.txt"
    claude_stderr_path = run_dir / "claude.stderr.txt"

    common_env = os.environ.copy()
    git_bash = _detect_git_bash()
    if git_bash:
        common_env.setdefault("CLAUDE_CODE_GIT_BASH_PATH", git_bash)

    codex_prompt = build_codex_prompt(prompt, profile, context_packet)
    small_context = build_claude_context_block(profile, tree_text, context_files)

    _write_text(run_dir / "user_prompt.txt", prompt)
    _write_text(run_dir / "context_packet.txt", context_packet)
    _write_text(run_dir / "codex_prompt.txt", codex_prompt)

    if strategy == "parallel":
        claude_prompt = build_claude_prompt(prompt, profile, None, "not_run", small_context)
        _write_text(run_dir / "claude_prompt.txt", claude_prompt)
        results = _run_parallel_tasks(
            [
                (
                    "codex",
                    _build_codex_command(codex_cmd, codex_output_path, codex_sandbox, workdir),
                    codex_prompt,
                    codex_output_path,
                    codex_stdout_path,
                    codex_stderr_path,
                ),
                (
                    "claude",
                    _build_claude_command(claude_cmd),
                    claude_prompt,
                    claude_output_path,
                    claude_stdout_path,
                    claude_stderr_path,
                ),
            ],
            workdir,
            common_env,
            timeout_sec,
        )
        codex_result = results["codex"]
        claude_result = results["claude"]
    else:
        codex_result = _run_process(
            name="codex",
            command=_build_codex_command(codex_cmd, codex_output_path, codex_sandbox, workdir),
            stdin_text=codex_prompt,
            cwd=workdir,
            env=common_env,
            timeout_sec=timeout_sec,
            output_path=codex_output_path,
            stdout_path=codex_stdout_path,
            stderr_path=codex_stderr_path,
        )
        claude_status = "ok" if codex_result.success else f"failed rc={codex_result.returncode}"
        claude_prompt = build_claude_prompt(prompt, profile, codex_result.output, claude_status, small_context)
        _write_text(run_dir / "claude_prompt.txt", claude_prompt)
        claude_result = _run_process(
            name="claude",
            command=_build_claude_command(claude_cmd),
            stdin_text=claude_prompt,
            cwd=workdir,
            env=common_env,
            timeout_sec=timeout_sec,
            output_path=claude_output_path,
            stdout_path=claude_stdout_path,
            stderr_path=claude_stderr_path,
        )

    summary = _compose_summary(codex_result, claude_result)
    _write_text(
        run_dir / "meta.json",
        _render_meta(
            prompt=prompt,
            workdir=workdir,
            strategy=strategy,
            profile=profile,
            config_path=config_path,
            context_files=context_files,
            codex=codex_result,
            claude=claude_result,
        ),
    )
    _write_text(run_dir / "summary.txt", summary)

    return ExecutionResult(
        mode="orchestrated",
        strategy=strategy,
        workspace_path=str(workdir),
        artifact_dir=str(run_dir),
        summary=summary,
        codex=codex_result,
        claude=claude_result,
        git=None,
    )

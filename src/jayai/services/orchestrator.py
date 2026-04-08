from __future__ import annotations

import json
import locale
import os
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Sequence

from ..config import get_settings
from ..models import Project
from .project_context import (
    ContextFile,
    ProjectProfile,
    build_claude_context_block,
    build_claude_prompt,
    build_codex_prompt,
    clip,
    collect_context_files,
    extract_section,
    load_project_profile,
    render_context_packet,
    render_tree,
)


settings = get_settings()
ProgressCallback = Callable[[str, str], None]
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
    mode: Literal["codex", "claude", "both"]
    strategy: str
    workspace_path: str
    artifact_dir: str | None
    summary: str
    codex: AgentResult | None
    claude: AgentResult | None


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


def _read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _decode_output(payload: bytes | None) -> str:
    data = payload or b""
    for encoding in ("utf-8", locale.getpreferredencoding(False), "cp949"):
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _pump_stream(stream: object, sink: bytearray) -> None:
    reader = getattr(stream, "read", None)
    if reader is None:
        return
    while True:
        chunk = reader(4096)
        if not chunk:
            break
        sink.extend(chunk)


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
    phase_label: str,
    progress_callback: ProgressCallback | None = None,
) -> AgentResult:
    started = time.perf_counter()
    stdout_bytes = bytearray()
    stderr_bytes = bytearray()
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        if process.stdin:
            process.stdin.write(stdin_text.encode("utf-8"))
            process.stdin.close()

        stdout_thread = threading.Thread(target=_pump_stream, args=(process.stdout, stdout_bytes), daemon=True)
        stderr_thread = threading.Thread(target=_pump_stream, args=(process.stderr, stderr_bytes), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        while True:
            returncode = process.poll()
            elapsed_sec = int(time.perf_counter() - started)
            streamed_output = _read_if_exists(output_path)
            if not streamed_output:
                streamed_output = _decode_output(bytes(stdout_bytes))
            streamed_error = _decode_output(bytes(stderr_bytes))
            if progress_callback:
                preview = streamed_output.strip() or streamed_error.strip() or f"{name} running... {elapsed_sec}s"
                progress_callback(phase_label, preview)
            if returncode is not None:
                break
            if time.perf_counter() - started > timeout_sec:
                process.kill()
                raise subprocess.TimeoutExpired(command, timeout_sec, output=bytes(stdout_bytes), stderr=bytes(stderr_bytes))
            time.sleep(0.75)

        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

        duration = time.perf_counter() - started
        stdout = _decode_output(bytes(stdout_bytes))
        stderr = _decode_output(bytes(stderr_bytes))
        _write_text(stdout_path, stdout)
        _write_text(stderr_path, stderr)
        output = _read_if_exists(output_path) or stdout
        if not output_path.exists():
            _write_text(output_path, output)
        return _build_agent_result(
            name=name,
            command=command,
            returncode=process.returncode or 0,
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
        stdout = _decode_output(exc.stdout if exc.stdout is not None else bytes(stdout_bytes))
        stderr = _decode_output(exc.stderr if exc.stderr is not None else bytes(stderr_bytes))
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


def _build_shared_prompt(
    *,
    project: Project,
    prompt: str,
    handoff_text: str,
) -> str:
    lines = [
        f"Project title: {project.title}",
        f"Project slug: {project.slug}",
        f"Default branch: {project.default_branch}",
        f"Repo: {project.repo_url or '(none)'}",
        "",
    ]
    if handoff_text.strip():
        lines.extend(["CURRENT_HANDOFF", handoff_text.strip(), ""])
    lines.extend(["USER_REQUEST", prompt.strip()])
    return "\n".join(lines).strip()


def _compose_summary(mode: Literal["codex", "claude", "both"], codex: AgentResult | None, claude: AgentResult | None) -> str:
    chunks: list[str] = []
    if codex and (codex.final or codex.project_context):
        chunks.append("[Codex]\n" + (codex.final or codex.output.strip()))
    if claude and (claude.final or claude.critique or claude.follow_up):
        if claude.final:
            chunks.append("[Claude]\n" + claude.final)
        if claude.critique:
            chunks.append("[Claude Critique]\n" + claude.critique)
        if claude.follow_up:
            chunks.append("[Claude Follow Up]\n" + claude.follow_up)

    if not chunks:
        if codex:
            chunks.append(f"[Codex]\n{clip(codex.output, 6000)}")
        if claude:
            chunks.append(f"[Claude]\n{clip(claude.output, 6000)}")

    if mode == "codex" and codex and not chunks:
        chunks.append(codex.output)
    if mode == "claude" and claude and not chunks:
        chunks.append(claude.output)
    return "\n\n".join(chunk for chunk in chunks if chunk).strip()


def _render_meta(
    *,
    prompt: str,
    mode: str,
    workdir: Path,
    profile: ProjectProfile,
    config_path: Path | None,
    context_files: list[ContextFile],
    codex: AgentResult | None,
    claude: AgentResult | None,
) -> str:
    payload = {
        "prompt": prompt,
        "mode": mode,
        "workdir": str(workdir),
        "project_name": profile.project_name,
        "config_path": str(config_path) if config_path else "",
        "hostname": socket.gethostname(),
        "context_files": [asdict(item) for item in context_files],
        "codex": asdict(codex) if codex else None,
        "claude": asdict(claude) if claude else None,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def execute_user_task(
    *,
    project: Project,
    workspace_path: str,
    prompt: str,
    handoff_text: str = "",
    mode: Literal["codex", "claude", "both"] = "both",
    timeout_sec: int = 900,
    codex_sandbox: str = "workspace-write",
    progress_callback: ProgressCallback | None = None,
) -> ExecutionResult:
    workdir = Path(workspace_path).expanduser().resolve()
    if not workdir.exists() or not workdir.is_dir():
        raise RuntimeError(f"workspace path not found: {workdir}")

    if progress_callback:
        progress_callback("preparing workspace", f"workspace: {workdir}")

    profile, config_path, _ = load_project_profile(workdir, docs_globs=project.docs_globs)
    context_files = collect_context_files(workdir, profile)
    tree_text = render_tree(workdir, profile)
    context_packet = render_context_packet(profile, config_path, context_files, tree_text)
    shared_prompt = _build_shared_prompt(project=project, prompt=prompt, handoff_text=handoff_text)
    small_context = build_claude_context_block(profile, tree_text, context_files)

    if progress_callback:
        progress_callback(
            "context ready",
            f"context files: {len(context_files)}\nmode: {mode}\nstrategy: {'codex_then_claude' if mode == 'both' else mode}",
        )

    codex_cmd = _detect_cmd("codex", WINDOWS_CODEX_CANDIDATES) if mode in {"codex", "both"} else ""
    claude_cmd = _detect_cmd("claude", WINDOWS_CLAUDE_CANDIDATES) if mode in {"claude", "both"} else ""

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

    codex_result: AgentResult | None = None
    claude_result: AgentResult | None = None

    _write_text(run_dir / "user_prompt.txt", prompt)
    _write_text(run_dir / "shared_prompt.txt", shared_prompt)
    _write_text(run_dir / "context_packet.txt", context_packet)

    if mode in {"codex", "both"}:
        codex_prompt = build_codex_prompt(shared_prompt, profile, context_packet)
        _write_text(run_dir / "codex_prompt.txt", codex_prompt)
        if progress_callback:
            progress_callback("starting Codex", "starting Codex")
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
            phase_label="running Codex",
            progress_callback=progress_callback,
        )

    if mode in {"claude", "both"}:
        codex_status = "not_run"
        codex_output = None
        if codex_result:
            codex_status = "ok" if codex_result.success else f"failed rc={codex_result.returncode}"
            codex_output = codex_result.output
        claude_prompt = build_claude_prompt(shared_prompt, profile, codex_output, codex_status, small_context)
        _write_text(run_dir / "claude_prompt.txt", claude_prompt)
        if progress_callback:
            progress_callback("starting Claude review", "starting Claude review")
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
            phase_label="running Claude review",
            progress_callback=progress_callback,
        )

    summary = _compose_summary(mode, codex_result, claude_result)
    _write_text(
        run_dir / "meta.json",
        _render_meta(
            prompt=prompt,
            mode=mode,
            workdir=workdir,
            profile=profile,
            config_path=config_path,
            context_files=context_files,
            codex=codex_result,
            claude=claude_result,
        ),
    )
    _write_text(run_dir / "summary.txt", summary)

    if progress_callback:
        progress_callback("completed", summary or "completed")

    strategy = {
        "codex": "codex_only",
        "claude": "claude_only",
        "both": "codex_then_claude",
    }[mode]
    return ExecutionResult(
        mode=mode,
        strategy=strategy,
        workspace_path=str(workdir),
        artifact_dir=str(run_dir),
        summary=summary,
        codex=codex_result,
        claude=claude_result,
    )

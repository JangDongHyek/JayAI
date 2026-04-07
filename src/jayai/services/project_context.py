from __future__ import annotations

import json
import locale
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


DEFAULT_PROJECT_CONFIG_NAMES = [".jayai.json", "jayai.json", ".orchestrator.json", "orchestrator.json"]
DEFAULT_CONTEXT_PATTERNS = [
    "AGENTS.md",
    "README.md",
    "README*.md",
    "CLAUDE.md",
    "SESSION_STATUS.md",
    "docs/**/*.md",
]
DEFAULT_IGNORE_DIRS = [
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "out",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "runs",
]


@dataclass
class ContextFile:
    relative_path: str
    size_bytes: int
    chars_loaded: int
    truncated: bool
    content: str


@dataclass
class ProjectProfile:
    project_name: str = ""
    strategy: str = "auto"
    heavy_context_agent: str = "codex"
    context_files: list[str] = field(default_factory=lambda: list(DEFAULT_CONTEXT_PATTERNS))
    claude_context_files: list[str] = field(default_factory=list)
    ignore_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORE_DIRS))
    tree_max_depth: int = 3
    tree_max_entries: int = 200
    context_max_chars_per_file: int = 12000
    context_max_total_chars: int = 40000
    codex_role: str = (
        "Deep reader and implementer. Read project context thoroughly, identify concrete constraints, "
        "and produce an execution-minded handoff."
    )
    claude_role: str = (
        "Reviewer and second-opinion specialist. Challenge weak assumptions, highlight risks, and "
        "propose sharper alternatives using Codex handoff as primary context."
    )
    share_tree_with_claude: bool = True
    share_docs_with_claude: bool = False


def decode_bytes(payload: bytes | None) -> str:
    data = payload or b""
    for encoding in ("utf-8", locale.getpreferredencoding(False), "cp949"):
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def read_text_file(path: Path) -> str:
    return decode_bytes(path.read_bytes())


def clip(text: str, limit: int = 600) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]..."


def normalize_profile(data: dict[str, Any], workdir: Path, docs_globs: Sequence[str] | None = None) -> ProjectProfile:
    profile = ProjectProfile()
    if docs_globs:
        profile.context_files = list(docs_globs)
    for key, value in data.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    if not profile.project_name:
        profile.project_name = workdir.name
    if profile.strategy not in {"auto", "parallel", "codex_first"}:
        profile.strategy = "auto"
    if profile.heavy_context_agent not in {"codex", "claude", "both"}:
        profile.heavy_context_agent = "codex"
    return profile


def locate_project_config(workdir: Path, explicit: str = "") -> Path | None:
    if explicit:
        config_path = Path(explicit).expanduser()
        if not config_path.is_absolute():
            config_path = workdir / config_path
        config_path = config_path.resolve()
        return config_path if config_path.exists() else None
    for name in DEFAULT_PROJECT_CONFIG_NAMES:
        candidate = workdir / name
        if candidate.exists():
            return candidate
    return None


def load_project_profile(
    workdir: Path,
    docs_globs: Sequence[str] | None = None,
    explicit: str = "",
) -> tuple[ProjectProfile, Path | None, dict[str, Any]]:
    config_path = locate_project_config(workdir, explicit)
    if not config_path:
        return normalize_profile({}, workdir, docs_globs), None, {}
    raw = json.loads(read_text_file(config_path))
    return normalize_profile(raw, workdir, docs_globs), config_path, raw


def should_ignore_path(path: Path, root: Path, ignore_dirs: Sequence[str]) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    parts = set(relative.parts)
    return any(name in parts for name in ignore_dirs)


def collect_context_files(workdir: Path, profile: ProjectProfile) -> list[ContextFile]:
    seen: set[str] = set()
    matched: list[Path] = []
    for pattern in profile.context_files:
        for path in workdir.glob(pattern):
            if not path.is_file():
                continue
            if should_ignore_path(path, workdir, profile.ignore_dirs):
                continue
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            matched.append(path.resolve())

    matched.sort(key=lambda item: str(item).lower())
    remaining = profile.context_max_total_chars
    context_files: list[ContextFile] = []
    for path in matched:
        if remaining <= 0:
            break
        raw_text = read_text_file(path)
        per_file_limit = min(profile.context_max_chars_per_file, remaining)
        truncated = len(raw_text) > per_file_limit
        content = raw_text[:per_file_limit]
        remaining -= len(content)
        context_files.append(
            ContextFile(
                relative_path=str(path.relative_to(workdir)),
                size_bytes=path.stat().st_size,
                chars_loaded=len(content),
                truncated=truncated,
                content=content,
            )
        )
    return context_files


def render_tree(workdir: Path, profile: ProjectProfile) -> str:
    lines = [workdir.name]
    emitted = 1
    truncated = False

    def walk(path: Path, depth: int) -> None:
        nonlocal emitted, truncated
        if truncated or depth > profile.tree_max_depth:
            return
        try:
            children = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        except PermissionError:
            lines.append("  " * depth + "[permission denied]")
            emitted += 1
            return
        for child in children:
            if should_ignore_path(child, workdir, profile.ignore_dirs):
                continue
            if emitted >= profile.tree_max_entries:
                truncated = True
                lines.append("  " * depth + "... tree truncated ...")
                return
            marker = "[D]" if child.is_dir() else "-"
            lines.append(f"{'  ' * depth}{marker} {child.name}")
            emitted += 1
            if child.is_dir():
                walk(child, depth + 1)
                if truncated:
                    return

    walk(workdir, 1)
    return "\n".join(lines)


def render_context_packet(
    profile: ProjectProfile,
    config_path: Path | None,
    context_files: list[ContextFile],
    tree_text: str,
) -> str:
    lines = [
        "PROJECT_PROFILE",
        f"- project_name: {profile.project_name}",
        f"- strategy: {profile.strategy}",
        f"- heavy_context_agent: {profile.heavy_context_agent}",
        f"- config_path: {config_path if config_path else '(none)'}",
        "",
        "FILE_TREE",
        tree_text,
        "",
        "CONTEXT_FILES",
    ]
    if not context_files:
        lines.append("(none)")
        return "\n".join(lines).strip() + "\n"
    for item in context_files:
        lines.extend(
            [
                f"--- FILE: {item.relative_path}",
                f"size_bytes={item.size_bytes} chars_loaded={item.chars_loaded} truncated={str(item.truncated).lower()}",
                item.content.rstrip(),
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def build_codex_prompt(user_prompt: str, profile: ProjectProfile, context_packet: str) -> str:
    return (
        f"You are the Codex branch of JayAI.\n\n"
        f"Your role:\n{profile.codex_role}\n\n"
        "Primary expectations:\n"
        "- This subtask is already approved by the user. Do not ask for permission again.\n"
        "- Treat the supplied project context packet as the initial source of truth.\n"
        "- Read deeply. Surface concrete constraints, architecture cues, and likely implementation impact.\n"
        "- If key information is missing, say what is missing instead of guessing.\n"
        "- Be concise but specific.\n\n"
        f"User task:\n{user_prompt}\n\n"
        "Return plain text with these exact section headers:\n"
        "[FINAL]\n"
        "- direct answer or execution-minded response for the user task\n\n"
        "[PROJECT_CONTEXT]\n"
        "- what project docs/tree imply\n\n"
        "[HANDOFF_FOR_CLAUDE]\n"
        "- compressed handoff for Claude\n\n"
        "Project context packet follows.\n"
        f"{context_packet}"
    ).strip()


def build_claude_context_block(profile: ProjectProfile, tree_text: str, context_files: list[ContextFile]) -> str:
    lines: list[str] = []
    if profile.share_tree_with_claude:
        lines.extend(["OPTIONAL_SMALL_CONTEXT", "FILE_TREE", tree_text, ""])
    if profile.share_docs_with_claude and context_files:
        lines.append("DOC_EXCERPTS")
        for item in context_files:
            lines.extend([f"--- FILE: {item.relative_path}", clip(item.content, 2000), ""])
    return "\n".join(lines).strip()


def extract_section(text: str, section_name: str) -> str:
    pattern = re.compile(
        rf"^\[{re.escape(section_name)}\]\s*(.*?)(?=^\[[A-Z0-9_]+\]\s*|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def build_claude_prompt(
    user_prompt: str,
    profile: ProjectProfile,
    codex_output: str | None,
    codex_status: str,
    small_context: str,
) -> str:
    codex_handoff = ""
    codex_final = ""
    codex_project_context = ""
    if codex_output:
        codex_handoff = extract_section(codex_output, "HANDOFF_FOR_CLAUDE") or clip(codex_output, 4000)
        codex_final = extract_section(codex_output, "FINAL")
        codex_project_context = extract_section(codex_output, "PROJECT_CONTEXT")

    parts = [
        "You are the Claude branch of JayAI.",
        "",
        "Your role:",
        profile.claude_role,
        "",
        "Primary expectations:",
        "- This subtask is already approved by the user. Do not ask for permission again.",
        "- Use Codex handoff as the main repo context.",
        "- Challenge weak assumptions and call out risks or better options.",
        "- Do not pretend you personally read more project files than were provided.",
        "- Be concise but sharp.",
        "",
        "User task:",
        user_prompt,
        "",
        f"Codex status: {codex_status}",
        "",
        "Codex final response:",
        codex_final or "(none)",
        "",
        "Codex project context:",
        codex_project_context or "(none)",
        "",
        "Codex handoff:",
        codex_handoff or "(none)",
    ]
    if small_context:
        parts.extend(["", small_context])
    parts.extend(
        [
            "",
            "Return plain text with these exact section headers:",
            "[FINAL]",
            "- your direct answer, review, or second opinion",
            "",
            "[CRITIQUE]",
            "- flaws, risks, disagreements, or stronger framing",
            "",
            "[FOLLOW_UP]",
            "- concrete next steps or checks",
        ]
    )
    return "\n".join(parts).strip()


def resolve_strategy(profile: ProjectProfile, has_context: bool) -> str:
    if profile.strategy != "auto":
        return profile.strategy
    if has_context and profile.heavy_context_agent == "codex":
        return "codex_first"
    return "parallel"

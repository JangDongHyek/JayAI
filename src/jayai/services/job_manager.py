from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from ..models import Project
from ..schemas import LocalJobRead
from .orchestrator import execute_user_task


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class JobState:
    id: str
    project_id: int
    kind: str
    mode: str | None
    status: Literal["queued", "running", "completed", "failed"]
    phase: str
    prompt: str | None
    output: str = ""
    error: str | None = None
    workspace_path: str | None = None
    artifact_dir: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None

    def to_read(self) -> LocalJobRead:
        return LocalJobRead(
            id=self.id,
            project_id=self.project_id,
            kind=self.kind,
            mode=self.mode,
            status=self.status,
            phase=self.phase,
            prompt=self.prompt,
            output=self.output,
            error=self.error,
            workspace_path=self.workspace_path,
            artifact_dir=self.artifact_dir,
            started_at=self.started_at,
            finished_at=self.finished_at,
        )


class LocalJobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobState] = {}
        self._active_job_id: str | None = None

    def start_execution(
        self,
        *,
        project: Project,
        workspace_path: str,
        prompt: str,
        handoff_text: str,
        mode: Literal["codex", "claude", "both"],
    ) -> LocalJobRead:
        with self._lock:
            if self._active_job_id:
                active = self._jobs[self._active_job_id]
                if active.status in {"queued", "running"}:
                    raise RuntimeError("현재 실행 중인 작업이 끝나지 않았음")

            job = JobState(
                id=uuid.uuid4().hex,
                project_id=project.id,
                kind="execution",
                mode=mode,
                status="queued",
                phase="대기 중",
                prompt=prompt,
                workspace_path=workspace_path,
            )
            self._jobs[job.id] = job
            self._active_job_id = job.id

        thread = threading.Thread(
            target=self._run_execution_job,
            kwargs={
                "job_id": job.id,
                "project": project,
                "workspace_path": workspace_path,
                "prompt": prompt,
                "handoff_text": handoff_text,
                "mode": mode,
            },
            daemon=True,
        )
        thread.start()
        return job.to_read()

    def _run_execution_job(
        self,
        *,
        job_id: str,
        project: Project,
        workspace_path: str,
        prompt: str,
        handoff_text: str,
        mode: Literal["codex", "claude", "both"],
    ) -> None:
        self._update(job_id, status="running", phase=self._phase_for_mode(mode))
        try:
            result = execute_user_task(
                project=project,
                workspace_path=workspace_path,
                prompt=prompt,
                handoff_text=handoff_text,
                mode=mode,
            )
            self._update(
                job_id,
                status="completed",
                phase="완료",
                output=result.summary,
                artifact_dir=result.artifact_dir,
                finished_at=utc_now(),
            )
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                phase="실패",
                error=str(exc),
                output=str(exc),
                finished_at=utc_now(),
            )
        finally:
            with self._lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None

    def _phase_for_mode(self, mode: Literal["codex", "claude", "both"]) -> str:
        return {
            "codex": "Codex 실행 중",
            "claude": "Claude 실행 중",
            "both": "Codex 실행 후 Claude 검토 중",
        }[mode]

    def _update(
        self,
        job_id: str,
        *,
        status: Literal["queued", "running", "completed", "failed"] | None = None,
        phase: str | None = None,
        output: str | None = None,
        error: str | None = None,
        artifact_dir: str | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if status is not None:
                job.status = status
            if phase is not None:
                job.phase = phase
            if output is not None:
                job.output = output
            if error is not None:
                job.error = error
            if artifact_dir is not None:
                job.artifact_dir = artifact_dir
            if finished_at is not None:
                job.finished_at = finished_at

    def get(self, job_id: str) -> LocalJobRead:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise RuntimeError("job not found")
            return job.to_read()

    def active(self) -> LocalJobRead | None:
        with self._lock:
            if not self._active_job_id:
                return None
            job = self._jobs.get(self._active_job_id)
            return job.to_read() if job else None


job_manager = LocalJobManager()

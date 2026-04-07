from __future__ import annotations

from fastapi import APIRouter

from ..schemas import RunnerProbeRequest, RunnerProbeResponse, WorkspaceScanRequest, WorkspaceScanResponse
from ..services.runner import probe_local_environment, scan_workspace


router = APIRouter(prefix="/api/runner", tags=["runner"])


@router.post("/probe", response_model=RunnerProbeResponse)
def probe_runner(payload: RunnerProbeRequest) -> RunnerProbeResponse:
    return probe_local_environment(payload.workdir)


@router.post("/scan-workspace", response_model=WorkspaceScanResponse)
def scan_runner_workspace(payload: WorkspaceScanRequest) -> WorkspaceScanResponse:
    return scan_workspace(payload.path)


from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Project, ProjectHandoff, WorkspaceBinding
from ..schemas import (
    ProjectCreate,
    ProjectDetailRead,
    ProjectHandoffRead,
    ProjectHandoffUpsert,
    ProjectRead,
    ProjectUpdate,
    WorkspaceBindingCreate,
    WorkspaceBindingRead,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _default_handoff(project_id: int) -> ProjectHandoffRead:
    return ProjectHandoffRead(project_id=project_id)


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.updated_at.desc())))


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    existing = db.scalar(select(Project).where(Project.slug == payload.slug))
    if existing:
        raise HTTPException(status_code=409, detail="project slug already exists")
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    return _get_project_or_404(project_id, db)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
) -> Project:
    project = _get_project_or_404(project_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}/detail", response_model=ProjectDetailRead)
def get_project_detail(project_id: int, db: Session = Depends(get_db)) -> ProjectDetailRead:
    project = _get_project_or_404(project_id, db)
    bindings = list(
        db.scalars(
            select(WorkspaceBinding)
            .where(WorkspaceBinding.project_id == project_id)
            .order_by(WorkspaceBinding.updated_at.desc())
        )
    )
    handoff = db.scalar(select(ProjectHandoff).where(ProjectHandoff.project_id == project_id))
    return ProjectDetailRead(
        project=ProjectRead.model_validate(project),
        bindings=[WorkspaceBindingRead.model_validate(item) for item in bindings],
        handoff=ProjectHandoffRead.model_validate(handoff) if handoff else _default_handoff(project_id),
    )


@router.get("/{project_id}/bindings", response_model=list[WorkspaceBindingRead])
def list_bindings(project_id: int, db: Session = Depends(get_db)) -> list[WorkspaceBinding]:
    _get_project_or_404(project_id, db)
    return list(
        db.scalars(
            select(WorkspaceBinding)
            .where(WorkspaceBinding.project_id == project_id)
            .order_by(WorkspaceBinding.updated_at.desc())
        )
    )


@router.post("/{project_id}/bindings", response_model=WorkspaceBindingRead, status_code=status.HTTP_201_CREATED)
def bind_workspace(
    project_id: int,
    payload: WorkspaceBindingCreate,
    db: Session = Depends(get_db),
) -> WorkspaceBinding:
    _get_project_or_404(project_id, db)
    if payload.project_id != project_id:
        raise HTTPException(status_code=400, detail="project_id mismatch")
    binding = db.scalar(
        select(WorkspaceBinding).where(
            WorkspaceBinding.project_id == payload.project_id,
            WorkspaceBinding.device_id == payload.device_id,
        )
    )
    if binding:
        binding.local_path = payload.local_path
        binding.preferred_branch = payload.preferred_branch
    else:
        binding = WorkspaceBinding(**payload.model_dump())
        db.add(binding)
    db.commit()
    db.refresh(binding)
    return binding


@router.get("/{project_id}/handoff", response_model=ProjectHandoffRead)
def get_handoff(project_id: int, db: Session = Depends(get_db)) -> ProjectHandoffRead:
    _get_project_or_404(project_id, db)
    handoff = db.scalar(select(ProjectHandoff).where(ProjectHandoff.project_id == project_id))
    return ProjectHandoffRead.model_validate(handoff) if handoff else _default_handoff(project_id)


@router.put("/{project_id}/handoff", response_model=ProjectHandoffRead)
def save_handoff(
    project_id: int,
    payload: ProjectHandoffUpsert,
    db: Session = Depends(get_db),
) -> ProjectHandoff:
    _get_project_or_404(project_id, db)
    handoff = db.scalar(select(ProjectHandoff).where(ProjectHandoff.project_id == project_id))
    if not handoff:
        handoff = ProjectHandoff(project_id=project_id)
        db.add(handoff)
    for key, value in payload.model_dump().items():
        setattr(handoff, key, value)
    db.commit()
    db.refresh(handoff)
    return handoff

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Conversation, Message, Project, WorkspaceBinding
from ..schemas import (
    ConversationCreate,
    ConversationRead,
    MessageCreate,
    MessageRead,
    ProjectCreate,
    ProjectRead,
    WorkspaceBindingCreate,
    WorkspaceBindingRead,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


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
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.get("/{project_id}/bindings", response_model=list[WorkspaceBindingRead])
def list_bindings(project_id: int, db: Session = Depends(get_db)) -> list[WorkspaceBinding]:
    return list(
        db.scalars(
            select(WorkspaceBinding)
            .where(WorkspaceBinding.project_id == project_id)
            .order_by(WorkspaceBinding.created_at.desc())
        )
    )


@router.post("/{project_id}/bindings", response_model=WorkspaceBindingRead, status_code=status.HTTP_201_CREATED)
def bind_workspace(
    project_id: int,
    payload: WorkspaceBindingCreate,
    db: Session = Depends(get_db),
) -> WorkspaceBinding:
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


@router.get("/{project_id}/conversations", response_model=list[ConversationRead])
def list_conversations(project_id: int, db: Session = Depends(get_db)) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.updated_at.desc())
        )
    )


@router.post(
    "/{project_id}/conversations",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    project_id: int,
    payload: ConversationCreate,
    db: Session = Depends(get_db),
) -> Conversation:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="project not found")
    conversation = Conversation(project_id=project_id, title=payload.title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(conversation_id: int, db: Session = Depends(get_db)) -> list[Message]:
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
) -> Message:
    if not db.get(Conversation, conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    message = Message(conversation_id=conversation_id, **payload.model_dump())
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


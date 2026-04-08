from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(120), default="main")
    docs_globs: Mapped[list[str]] = mapped_column(JSON, default=list)

    bindings: Mapped[list["WorkspaceBinding"]] = relationship(back_populates="project")
    handoff: Mapped["ProjectHandoff | None"] = relationship(back_populates="project", uselist=False)
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="project")


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    hostname: Mapped[str] = mapped_column(String(120))
    platform: Mapped[str] = mapped_column(String(120))
    is_server: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    bindings: Mapped[list["WorkspaceBinding"]] = relationship(back_populates="device")
    runs: Mapped[list["Run"]] = relationship(back_populates="device")


class WorkspaceBinding(TimestampMixin, Base):
    __tablename__ = "workspace_bindings"
    __table_args__ = (UniqueConstraint("project_id", "device_id", name="uq_project_device_binding"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    local_path: Mapped[str] = mapped_column(String(1000))
    preferred_branch: Mapped[str | None] = mapped_column(String(120), nullable=True)

    project: Mapped[Project] = relationship(back_populates="bindings")
    device: Mapped[Device] = relationship(back_populates="bindings")


class ProjectHandoff(TimestampMixin, Base):
    __tablename__ = "project_handoffs"
    __table_args__ = (UniqueConstraint("project_id", name="uq_project_handoff_project"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    project_brief: Mapped[str] = mapped_column(Text, default="")
    current_status: Mapped[str] = mapped_column(Text, default="")
    next_steps: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_by_device: Mapped[str | None] = mapped_column(String(120), nullable=True)

    project: Mapped[Project] = relationship(back_populates="handoff")


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), default="active")

    project: Mapped[Project] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")
    runs: Mapped[list["Run"]] = relationship(back_populates="conversation")


class Message(TimestampMixin, Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(50))
    agent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    model_hint: Mapped[str | None] = mapped_column(String(120), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Run(TimestampMixin, Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True, index=True)
    strategy: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    prompt_excerpt: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="runs")
    device: Mapped[Device | None] = relationship(back_populates="runs")

from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AgentRole, ApprovalStatus, ApprovalType, ArtifactType, EnvironmentStatus, PullRequestStatus, RunStatus, StepKind, StepStatus


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    repo_url: Mapped[str | None] = mapped_column(Text)
    local_repo_path: Mapped[str | None] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    inspect_command: Mapped[str | None] = mapped_column(Text)
    test_command: Mapped[str | None] = mapped_column(Text)
    build_command: Mapped[str | None] = mapped_column(Text)
    lint_command: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="run_status"), index=True, nullable=False, default=RunStatus.QUEUED)
    current_step_id: Mapped[str | None] = mapped_column(ForeignKey("steps.id", ondelete="SET NULL"))
    final_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    project = relationship("Project")
    steps = relationship("Step", back_populates="run", foreign_keys="Step.run_id", cascade="all, delete-orphan")


class Step(Base):
    __tablename__ = "steps"
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[StepKind] = mapped_column(Enum(StepKind, name="step_kind"), nullable=False)
    role: Mapped[AgentRole] = mapped_column(Enum(AgentRole, name="agent_role"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[StepStatus] = mapped_column(Enum(StepStatus, name="step_status"), index=True, nullable=False, default=StepStatus.QUEUED)
    input_json: Mapped[dict | None] = mapped_column(JSONB)
    output_json: Mapped[dict | None] = mapped_column(JSONB)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    run = relationship("Run", back_populates="steps", foreign_keys=[run_id])


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("steps.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("steps.id", ondelete="CASCADE"), index=True)
    artifact_type: Mapped[ArtifactType] = mapped_column(Enum(ArtifactType, name="artifact_type"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("steps.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    approval_type: Mapped[ApprovalType] = mapped_column(
        Enum(ApprovalType, name="approval_type", values_callable=lambda enum_cls: [item.value for item in enum_cls]),
        index=True,
        nullable=False,
        default=ApprovalType.GOVERNANCE,
    )
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus, name="approval_status"), index=True, nullable=False, default=ApprovalStatus.PENDING)
    requested_payload_json: Mapped[dict | None] = mapped_column(JSONB)
    response_payload_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExecutionEnvironment(Base):
    __tablename__ = "execution_environments"
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="docker")
    image: Mapped[str | None] = mapped_column(String(255))
    container_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[EnvironmentStatus] = mapped_column(Enum(EnvironmentStatus, name="environment_status"), index=True, nullable=False, default=EnvironmentStatus.CREATING)
    repo_dir: Mapped[str | None] = mapped_column(Text)
    branch_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PullRequest(Base):
    __tablename__ = "pull_requests"
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="github")
    repo: Mapped[str | None] = mapped_column(String(255))
    branch_name: Mapped[str | None] = mapped_column(String(255))
    pr_number: Mapped[int | None] = mapped_column(Integer)
    pr_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PullRequestStatus] = mapped_column(Enum(PullRequestStatus, name="pull_request_status"), index=True, nullable=False, default=PullRequestStatus.OPEN)
    merge_commit_sha: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

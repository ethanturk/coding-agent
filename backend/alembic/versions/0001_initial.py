"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_status = postgresql.ENUM("queued", "running", "waiting_for_human", "blocked", "failed", "completed", "cancelled", name="run_status")
    step_status = postgresql.ENUM("queued", "running", "waiting_for_human", "blocked", "failed", "completed", "cancelled", name="step_status")
    step_kind = postgresql.ENUM("planning", "implementation", "testing", "review", "reporting", name="step_kind")
    agent_role = postgresql.ENUM("orchestrator", "planner", "developer", "tester", "reviewer", "reporter", name="agent_role")
    approval_status = postgresql.ENUM("pending", "approved", "rejected", name="approval_status")
    artifact_type = postgresql.ENUM("log", "diff", "test_report", "summary", name="artifact_type")
    bind = op.get_bind()
    for enum in (run_status, step_status, step_kind, agent_role, approval_status, artifact_type):
        enum.create(bind, checkfirst=True)

    op.create_table("projects",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("repo_url", sa.Text()),
        sa.Column("local_repo_path", sa.Text()),
        sa.Column("default_branch", sa.String(length=255), nullable=False, server_default="main"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("slug"),
    )
    op.create_table("runs",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("project_id", sa.String(length=26), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", run_status, nullable=False, server_default="queued"),
        sa.Column("current_step_id", sa.String(length=26)),
        sa.Column("final_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table("steps",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("run_id", sa.String(length=26), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("kind", step_kind, nullable=False),
        sa.Column("role", agent_role, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("status", step_status, nullable=False, server_default="queued"),
        sa.Column("input_json", postgresql.JSONB()),
        sa.Column("output_json", postgresql.JSONB()),
        sa.Column("error_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_foreign_key("fk_runs_current_step_id_steps", "runs", "steps", ["current_step_id"], ["id"], ondelete="SET NULL")
    op.create_table("events",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("run_id", sa.String(length=26), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.String(length=26), sa.ForeignKey("steps.id", ondelete="CASCADE")),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table("artifacts",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("run_id", sa.String(length=26), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.String(length=26), sa.ForeignKey("steps.id", ondelete="CASCADE")),
        sa.Column("artifact_type", artifact_type, nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table("approvals",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("run_id", sa.String(length=26), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.String(length=26), sa.ForeignKey("steps.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("status", approval_status, nullable=False, server_default="pending"),
        sa.Column("requested_payload_json", postgresql.JSONB()),
        sa.Column("response_payload_json", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("approvals")
    op.drop_table("artifacts")
    op.drop_table("events")
    op.drop_constraint("fk_runs_current_step_id_steps", "runs", type_="foreignkey")
    op.drop_table("steps")
    op.drop_table("runs")
    op.drop_table("projects")

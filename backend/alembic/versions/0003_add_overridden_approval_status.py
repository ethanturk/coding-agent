"""add overridden approval status

Revision ID: 0003_override_status
Revises: 0002_add_approval_type
Create Date: 2026-04-26
"""

from alembic import op

revision = '0003_override_status'
down_revision = '0002_add_approval_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE approval_status ADD VALUE IF NOT EXISTS 'overridden'")


def downgrade() -> None:
    # PostgreSQL enums do not support removing individual values safely.
    pass

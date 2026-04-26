"""normalize approval status labels

Revision ID: 0004_norm_approval_status
Revises: 0003_override_status
Create Date: 2026-04-26
"""

from alembic import op

revision = '0004_norm_approval_status'
down_revision = '0003_override_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE approval_status RENAME VALUE 'PENDING' TO 'pending'")
    op.execute("ALTER TYPE approval_status RENAME VALUE 'APPROVED' TO 'approved'")
    op.execute("ALTER TYPE approval_status RENAME VALUE 'REJECTED' TO 'rejected'")


def downgrade() -> None:
    op.execute("ALTER TYPE approval_status RENAME VALUE 'pending' TO 'PENDING'")
    op.execute("ALTER TYPE approval_status RENAME VALUE 'approved' TO 'APPROVED'")
    op.execute("ALTER TYPE approval_status RENAME VALUE 'rejected' TO 'REJECTED'")

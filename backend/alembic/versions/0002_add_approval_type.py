"""add approval type

Revision ID: 0002_add_approval_type
Revises: 0001_initial
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002_add_approval_type'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    approval_type = postgresql.ENUM('edit_proposal', 'pr_merge', 'governance', name='approval_type')
    bind = op.get_bind()
    approval_type.create(bind, checkfirst=True)
    op.add_column('approvals', sa.Column('approval_type', approval_type, nullable=True))
    op.execute(
        """
        UPDATE approvals
        SET approval_type = CASE
            WHEN requested_payload_json ? 'proposals' OR requested_payload_json ? 'path' THEN 'edit_proposal'
            ELSE 'governance'
        END
        WHERE approval_type IS NULL
        """
    )
    op.alter_column('approvals', 'approval_type', nullable=False, server_default='governance')
    op.create_index('ix_approvals_approval_type', 'approvals', ['approval_type'])


def downgrade() -> None:
    op.drop_index('ix_approvals_approval_type', table_name='approvals')
    op.drop_column('approvals', 'approval_type')
    approval_type = postgresql.ENUM('edit_proposal', 'pr_merge', 'governance', name='approval_type')
    approval_type.drop(op.get_bind(), checkfirst=True)

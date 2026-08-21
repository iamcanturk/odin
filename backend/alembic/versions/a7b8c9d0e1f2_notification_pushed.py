"""add notifications.pushed_at

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-21 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('notifications', sa.Column('pushed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_notifications_pushed_at', 'notifications', ['pushed_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_notifications_pushed_at', table_name='notifications')
    op.drop_column('notifications', 'pushed_at')

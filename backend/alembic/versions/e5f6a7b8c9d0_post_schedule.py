"""add posts.scheduled_for + reminded_at

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-21 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('posts', sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True))
    op.add_column('posts', sa.Column('reminded_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_posts_scheduled_for', 'posts', ['scheduled_for'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_posts_scheduled_for', table_name='posts')
    op.drop_column('posts', 'reminded_at')
    op.drop_column('posts', 'scheduled_for')

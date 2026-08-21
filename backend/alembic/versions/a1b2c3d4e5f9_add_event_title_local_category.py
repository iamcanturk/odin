"""add event title_local + category

Revision ID: a1b2c3d4e5f9
Revises: f3c4d5e6a708
Create Date: 2026-08-19 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f9'
down_revision: Union[str, Sequence[str], None] = 'f3c4d5e6a708'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('events', sa.Column('title_local', sa.String(length=1000), nullable=True))
    op.add_column('events', sa.Column('category', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_events_category'), 'events', ['category'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_events_category'), table_name='events')
    op.drop_column('events', 'category')
    op.drop_column('events', 'title_local')

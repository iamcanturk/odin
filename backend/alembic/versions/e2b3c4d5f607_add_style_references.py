"""add style_references

Revision ID: e2b3c4d5f607
Revises: d1a2b3c4e5f6
Create Date: 2026-08-18 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2b3c4d5f607'
down_revision: Union[str, Sequence[str], None] = 'd1a2b3c4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('style_references',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('handle', sa.String(length=120), nullable=False),
    sa.Column('external_id', sa.String(length=128), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('url', sa.String(length=1000), nullable=True),
    sa.Column('likes', sa.Integer(), nullable=True),
    sa.Column('reposts', sa.Integer(), nullable=True),
    sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default='now()', nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('handle', 'external_id', name='uq_styleref_handle_extid')
    )
    op.create_index(op.f('ix_style_references_handle'), 'style_references', ['handle'], unique=False)
    op.create_index(
        op.f('ix_style_references_created_at'), 'style_references', ['created_at'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_style_references_created_at'), table_name='style_references')
    op.drop_index(op.f('ix_style_references_handle'), table_name='style_references')
    op.drop_table('style_references')

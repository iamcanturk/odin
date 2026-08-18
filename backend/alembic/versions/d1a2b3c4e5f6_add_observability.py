"""add llm_usage and run_logs (observability)

Revision ID: d1a2b3c4e5f6
Revises: c87731095685
Create Date: 2026-08-18 17:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd1a2b3c4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c87731095685'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('llm_usage',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('model', sa.String(length=120), nullable=False),
    sa.Column('purpose', sa.String(length=32), nullable=True),
    sa.Column('prompt_tokens', sa.Integer(), nullable=False),
    sa.Column('completion_tokens', sa.Integer(), nullable=False),
    sa.Column('cost_usd', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default='now()', nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_llm_usage_created_at'), 'llm_usage', ['created_at'], unique=False)
    op.create_table('run_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('sources_polled', sa.Integer(), nullable=False),
    sa.Column('items_created', sa.Integer(), nullable=False),
    sa.Column('events_created', sa.Integer(), nullable=False),
    sa.Column('errors', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default='now()', nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_run_logs_created_at'), 'run_logs', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_run_logs_created_at'), table_name='run_logs')
    op.drop_table('run_logs')
    op.drop_index(op.f('ix_llm_usage_created_at'), table_name='llm_usage')
    op.drop_table('llm_usage')

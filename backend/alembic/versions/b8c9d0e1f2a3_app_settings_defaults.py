"""app_settings timestamps need server defaults

The model's TimestampMixin declares server_default=func.now(), but the table's
migration created the columns NOT NULL with no default. Tests build schema from
metadata and so never saw it; production builds from migrations and could not
accept a single insert into app_settings.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-22 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    for column in ('created_at', 'updated_at'):
        op.alter_column(
            'app_settings',
            column,
            server_default=sa.text('now()'),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    for column in ('created_at', 'updated_at'):
        op.alter_column(
            'app_settings',
            column,
            server_default=None,
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )

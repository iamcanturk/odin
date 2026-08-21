"""add profile bio/name/location/website

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f9
Create Date: 2026-08-21 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('profile_snapshots', sa.Column('display_name', sa.String(length=200), nullable=True))
    op.add_column('profile_snapshots', sa.Column('bio', sa.Text(), nullable=True))
    op.add_column('profile_snapshots', sa.Column('location', sa.String(length=200), nullable=True))
    op.add_column('profile_snapshots', sa.Column('website', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('profile_snapshots', 'website')
    op.drop_column('profile_snapshots', 'location')
    op.drop_column('profile_snapshots', 'bio')
    op.drop_column('profile_snapshots', 'display_name')

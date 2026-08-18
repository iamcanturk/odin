"""add observed_tweets

Revision ID: f3c4d5e6a708
Revises: e2b3c4d5f607
Create Date: 2026-08-18 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3c4d5e6a708'
down_revision: Union[str, Sequence[str], None] = 'e2b3c4d5f607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('observed_tweets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('external_id', sa.String(length=128), nullable=False),
    sa.Column('author_handle', sa.String(length=120), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('url', sa.String(length=1000), nullable=True),
    sa.Column('lang', sa.String(length=16), nullable=True),
    sa.Column('likes', sa.Integer(), nullable=True),
    sa.Column('replies', sa.Integer(), nullable=True),
    sa.Column('reposts', sa.Integer(), nullable=True),
    sa.Column('bookmarks', sa.Integer(), nullable=True),
    sa.Column('impressions', sa.BigInteger(), nullable=True),
    sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('external_id', 'observed_at', name='uq_observed_tweet_sighting')
    )
    op.create_index(op.f('ix_observed_tweets_external_id'), 'observed_tweets', ['external_id'])
    op.create_index(op.f('ix_observed_tweets_author_handle'), 'observed_tweets', ['author_handle'])
    op.create_index(op.f('ix_observed_tweets_observed_at'), 'observed_tweets', ['observed_at'])
    op.create_index('ix_observed_tweets_velocity', 'observed_tweets', ['posted_at', 'impressions'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_observed_tweets_velocity', table_name='observed_tweets')
    op.drop_index(op.f('ix_observed_tweets_observed_at'), table_name='observed_tweets')
    op.drop_index(op.f('ix_observed_tweets_author_handle'), table_name='observed_tweets')
    op.drop_index(op.f('ix_observed_tweets_external_id'), table_name='observed_tweets')
    op.drop_table('observed_tweets')

"""add daily_count to ai_cache

Revision ID: a1f3c8e92b44
Revises: de08533be172
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1f3c8e92b44'
down_revision = 'de08533be172'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ai_cache', sa.Column('daily_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('ai_cache', 'daily_count')

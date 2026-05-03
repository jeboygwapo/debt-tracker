"""widen password_hash to String(128)

Revision ID: de08533be172
Revises: 127d5021bacd
Create Date: 2026-05-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'de08533be172'
down_revision: Union[str, Sequence[str], None] = '127d5021bacd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'password_hash',
            existing_type=sa.String(length=64),
            type_=sa.String(length=128),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'password_hash',
            existing_type=sa.String(length=128),
            type_=sa.String(length=64),
            existing_nullable=False,
        )

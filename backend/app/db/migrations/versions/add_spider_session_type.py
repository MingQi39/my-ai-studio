"""Add spider session type

Revision ID: add_spider_001
Revises: add_fitness_001
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_spider_001"
down_revision: Union[str, Sequence[str], None] = "add_fitness_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.alter_column(
            "session_type",
            existing_type=sa.Enum("chat", "travel", "fitness", name="sessiontype"),
            type_=sa.Enum("chat", "travel", "fitness", "spider", name="sessiontype"),
            existing_nullable=False,
            server_default="chat",
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.alter_column(
            "session_type",
            existing_type=sa.Enum("chat", "travel", "fitness", "spider", name="sessiontype"),
            type_=sa.Enum("chat", "travel", "fitness", name="sessiontype"),
            existing_nullable=False,
            server_default="chat",
        )

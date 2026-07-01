"""Add session_type column to sessions

Revision ID: add_session_type_001
Revises: add_adapter_type_001
Create Date: 2026-06-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_session_type_001"
down_revision: Union[str, Sequence[str], None] = "add_adapter_type_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "session_type",
                sa.Enum("chat", "travel", name="sessiontype"),
                nullable=False,
                server_default="chat",
            )
        )
        batch_op.create_index("ix_sessions_session_type", ["session_type"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_sessions_session_type")
        batch_op.drop_column("session_type")

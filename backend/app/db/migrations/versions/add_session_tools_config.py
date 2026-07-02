"""Add tools_config column to session_configs

Revision ID: add_session_tools_config_001
Revises: add_message_is_complete_001
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_session_tools_config_001"
down_revision: Union[str, Sequence[str], None] = "add_message_is_complete_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("session_configs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tools_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("session_configs", schema=None) as batch_op:
        batch_op.drop_column("tools_config")

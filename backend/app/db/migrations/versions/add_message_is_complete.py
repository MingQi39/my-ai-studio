"""Add is_complete column to messages

Revision ID: add_message_is_complete_001
Revises: add_session_type_001
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_message_is_complete_001"
down_revision: Union[str, Sequence[str], None] = "add_session_type_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_complete", sa.Boolean(), nullable=False, server_default=sa.true()),
        )

    # 历史流式占位消息：有内容但未写入 tokens_used，视为未完成
    op.execute(
        """
        UPDATE messages
        SET is_complete = 0
        WHERE role = 'assistant'
          AND tokens_used IS NULL
          AND (
            TRIM(COALESCE(content, '')) != ''
            OR TRIM(COALESCE(thinking_content, '')) != ''
          )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_column("is_complete")

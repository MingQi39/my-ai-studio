"""Add goal deadline, learning plan, and push settings to interview profiles.

Revision ID: interview_006
Revises: interview_005
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "interview_006"
down_revision: Union[str, Sequence[str], None] = "interview_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("interview_profiles") as batch_op:
        batch_op.add_column(sa.Column("target_deadline", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("push_time", sa.String(length=5), nullable=True))
        batch_op.add_column(
            sa.Column(
                "push_timezone",
                sa.String(length=64),
                nullable=False,
                server_default="Asia/Shanghai",
            )
        )
        batch_op.add_column(sa.Column("learning_plan", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("plan_generated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_push_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("interview_profiles") as batch_op:
        batch_op.drop_column("last_push_date")
        batch_op.drop_column("plan_generated_at")
        batch_op.drop_column("learning_plan")
        batch_op.drop_column("push_timezone")
        batch_op.drop_column("push_time")
        batch_op.drop_column("push_enabled")
        batch_op.drop_column("target_deadline")

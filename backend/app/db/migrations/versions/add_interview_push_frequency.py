"""Add push_frequency to interview profiles.

Revision ID: interview_007
Revises: interview_006
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "interview_007"
down_revision: Union[str, Sequence[str], None] = "interview_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("interview_profiles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "push_frequency",
                sa.String(length=20),
                nullable=False,
                server_default="weekdays",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("interview_profiles") as batch_op:
        batch_op.drop_column("push_frequency")

"""Add salary_band to interview profiles.

Revision ID: interview_003
Revises: interview_002
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "interview_003"
down_revision: Union[str, Sequence[str], None] = "interview_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("interview_profiles") as batch_op:
        batch_op.add_column(sa.Column("salary_band", sa.String(length=80), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("interview_profiles") as batch_op:
        batch_op.drop_column("salary_band")

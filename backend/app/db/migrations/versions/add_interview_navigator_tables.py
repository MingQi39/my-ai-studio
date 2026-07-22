"""Add Interview Navigator profile and resume-claim storage.

Revision ID: interview_001
Revises: add_spider_001
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "interview_001"
down_revision: Union[str, Sequence[str], None] = "add_spider_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.alter_column(
            "session_type",
            existing_type=sa.Enum("chat", "travel", "fitness", "spider", name="sessiontype"),
            type_=sa.Enum("chat", "travel", "fitness", "spider", "interview", name="sessiontype"),
            existing_nullable=False,
            server_default="chat",
        )

    op.create_table(
        "interview_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target_role", sa.String(length=120), nullable=True),
        sa.Column("target_level", sa.String(length=80), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_interview_profiles_user_id"),
    )
    op.create_index("ix_interview_profiles_user_id", "interview_profiles", ["user_id"], unique=False)
    op.create_table(
        "interview_claims",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="candidate"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["interview_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_claims_profile_id", "interview_claims", ["profile_id"], unique=False)
    op.create_index("ix_interview_claims_status", "interview_claims", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interview_claims_status", table_name="interview_claims")
    op.drop_index("ix_interview_claims_profile_id", table_name="interview_claims")
    op.drop_table("interview_claims")
    op.drop_index("ix_interview_profiles_user_id", table_name="interview_profiles")
    op.drop_table("interview_profiles")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.alter_column(
            "session_type",
            existing_type=sa.Enum("chat", "travel", "fitness", "spider", "interview", name="sessiontype"),
            type_=sa.Enum("chat", "travel", "fitness", "spider", name="sessiontype"),
            existing_nullable=False,
            server_default="chat",
        )

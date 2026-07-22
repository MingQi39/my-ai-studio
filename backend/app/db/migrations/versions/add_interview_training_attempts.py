"""Add training attempts, session events, and review-card lifecycle fields.

Revision ID: interview_004
Revises: interview_003
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "interview_004"
down_revision: Union[str, Sequence[str], None] = "interview_003"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_table("interview_training_attempts"):
        op.create_table(
            "interview_training_attempts",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "profile_id",
                sa.String(length=36),
                sa.ForeignKey("interview_profiles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("topic", sa.String(length=255), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("level", sa.String(length=10), nullable=False),
            sa.Column("focus_node", sa.String(length=80), nullable=False),
            sa.Column("route_nodes", sa.JSON(), nullable=False),
            sa.Column("atlas", sa.JSON(), nullable=False),
            sa.Column("category", sa.String(length=40), nullable=False),
            sa.Column("goal_snapshot", sa.JSON(), nullable=False),
            sa.Column("source_claim_ids", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("answers", sa.JSON(), nullable=False),
            sa.Column("evaluation", sa.JSON(), nullable=True),
            sa.Column("hint_level", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("review_card_id", sa.String(length=36), nullable=True),
            sa.Column("degraded_reason", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_interview_attempts_profile_id", "interview_training_attempts", ["profile_id"]
        )
        op.create_index("ix_interview_attempts_status", "interview_training_attempts", ["status"])

    if not _has_table("interview_session_events"):
        op.create_table(
            "interview_session_events",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "profile_id",
                sa.String(length=36),
                sa.ForeignKey("interview_profiles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "attempt_id",
                sa.String(length=36),
                sa.ForeignKey("interview_training_attempts.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(length=40), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("profile_id", "seq", name="uq_interview_events_profile_seq"),
        )
        op.create_index(
            "ix_interview_events_attempt_id", "interview_session_events", ["attempt_id"]
        )

    with op.batch_alter_table("interview_review_cards") as batch_op:
        if not _has_column("interview_review_cards", "status"):
            batch_op.add_column(
                sa.Column("status", sa.String(length=20), nullable=False, server_default="new")
            )
        if not _has_column("interview_review_cards", "attempt_id"):
            batch_op.add_column(sa.Column("attempt_id", sa.String(length=36), nullable=True))
        if not _has_column("interview_review_cards", "last_reviewed_at"):
            batch_op.add_column(
                sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True)
            )
        if not _has_column("interview_review_cards", "next_due_at"):
            batch_op.add_column(
                sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True)
            )
        if not _has_column("interview_review_cards", "successful_recall_count"):
            batch_op.add_column(
                sa.Column(
                    "successful_recall_count",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
        if not _has_column("interview_review_cards", "source_claim_ids"):
            batch_op.add_column(sa.Column("source_claim_ids", sa.JSON(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE interview_review_cards
            SET next_due_at = datetime(created_at, '+1 day')
            WHERE next_due_at IS NULL
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE interview_review_cards
            SET source_claim_ids = '[]'
            WHERE source_claim_ids IS NULL
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("interview_review_cards") as batch_op:
        for col in (
            "source_claim_ids",
            "successful_recall_count",
            "next_due_at",
            "last_reviewed_at",
            "attempt_id",
            "status",
        ):
            if _has_column("interview_review_cards", col):
                batch_op.drop_column(col)

    if _has_table("interview_session_events"):
        op.drop_index("ix_interview_events_attempt_id", table_name="interview_session_events")
        op.drop_table("interview_session_events")
    if _has_table("interview_training_attempts"):
        op.drop_index("ix_interview_attempts_status", table_name="interview_training_attempts")
        op.drop_index("ix_interview_attempts_profile_id", table_name="interview_training_attempts")
        op.drop_table("interview_training_attempts")

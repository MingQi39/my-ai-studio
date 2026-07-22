"""Add interview RAG question bank tables.

Revision ID: interview_005
Revises: interview_004
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "interview_005"
down_revision: Union[str, Sequence[str], None] = "interview_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_question_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_url", name="uq_interview_question_sources_url"),
    )
    op.create_table(
        "interview_question_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(length=36),
            sa.ForeignKey("interview_question_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_question", sa.Text(), nullable=False),
        sa.Column("normalized_question", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=80), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=False),
        sa.Column("source_section", sa.String(length=255), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("content_hash", name="uq_interview_question_items_hash"),
    )
    op.create_index("ix_interview_question_items_topic", "interview_question_items", ["topic"])
    op.create_index("ix_interview_question_items_level", "interview_question_items", ["level"])
    op.create_index("ix_interview_question_items_active", "interview_question_items", ["is_active"])

    op.create_table(
        "interview_question_embeddings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "item_id",
            sa.String(length=36),
            sa.ForeignKey("interview_question_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("vector", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("item_id", "model", name="uq_interview_question_emb_item_model"),
    )
    op.create_index(
        "ix_interview_question_embeddings_item_id",
        "interview_question_embeddings",
        ["item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_question_embeddings_item_id", table_name="interview_question_embeddings")
    op.drop_table("interview_question_embeddings")
    op.drop_index("ix_interview_question_items_active", table_name="interview_question_items")
    op.drop_index("ix_interview_question_items_level", table_name="interview_question_items")
    op.drop_index("ix_interview_question_items_topic", table_name="interview_question_items")
    op.drop_table("interview_question_items")
    op.drop_table("interview_question_sources")

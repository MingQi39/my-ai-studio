"""Add KAN interview review cards.

Revision ID: interview_002
Revises: interview_001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = "interview_002"
down_revision: Union[str, Sequence[str], None] = "interview_001"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.create_table("interview_review_cards", sa.Column("id", sa.String(36), primary_key=True), sa.Column("profile_id", sa.String(36), sa.ForeignKey("interview_profiles.id", ondelete="CASCADE"), nullable=False), sa.Column("topic", sa.String(255), nullable=False), sa.Column("question", sa.Text(), nullable=False), sa.Column("answer", sa.Text(), nullable=False), sa.Column("missing_nodes", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_interview_review_cards_profile_id", "interview_review_cards", ["profile_id"])
def downgrade() -> None:
    op.drop_index("ix_interview_review_cards_profile_id", table_name="interview_review_cards"); op.drop_table("interview_review_cards")

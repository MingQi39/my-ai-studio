"""Add fitness session type and fitness tables

Revision ID: add_fitness_001
Revises: add_session_tools_config_001
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_fitness_001"
down_revision: Union[str, Sequence[str], None] = "add_session_tools_config_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite stores enums as VARCHAR; recreate session_type with fitness value.
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.alter_column(
            "session_type",
            existing_type=sa.Enum("chat", "travel", name="sessiontype"),
            type_=sa.Enum("chat", "travel", "fitness", name="sessiontype"),
            existing_nullable=False,
            server_default="chat",
        )

    op.create_table(
        "fitness_goals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("daily_calorie_goal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_fitness_goals_user_id"),
    )
    op.create_index("ix_fitness_goals_user_id", "fitness_goals", ["user_id"], unique=False)

    op.create_table(
        "fitness_diary_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "meal_type",
            sa.Enum("breakfast", "lunch", "dinner", "snack", name="fitnessmealtype"),
            nullable=False,
        ),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("total_kcal", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fitness_diary_user_date",
        "fitness_diary_entries",
        ["user_id", "date"],
        unique=False,
    )
    op.create_index(
        "ix_fitness_diary_session_id",
        "fitness_diary_entries",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_fitness_diary_entries_user_id",
        "fitness_diary_entries",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_fitness_diary_entries_date",
        "fitness_diary_entries",
        ["date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fitness_diary_entries_date", table_name="fitness_diary_entries")
    op.drop_index("ix_fitness_diary_entries_user_id", table_name="fitness_diary_entries")
    op.drop_index("ix_fitness_diary_session_id", table_name="fitness_diary_entries")
    op.drop_index("ix_fitness_diary_user_date", table_name="fitness_diary_entries")
    op.drop_table("fitness_diary_entries")

    op.drop_index("ix_fitness_goals_user_id", table_name="fitness_goals")
    op.drop_table("fitness_goals")

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.alter_column(
            "session_type",
            existing_type=sa.Enum("chat", "travel", "fitness", name="sessiontype"),
            type_=sa.Enum("chat", "travel", name="sessiontype"),
            existing_nullable=False,
            server_default="chat",
        )

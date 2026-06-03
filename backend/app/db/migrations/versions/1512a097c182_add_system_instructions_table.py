"""Add system_instructions table

Revision ID: 1512a097c182
Revises: 6f46407ed01e
Create Date: 2026-01-23 15:38:00.100837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1512a097c182'
down_revision: Union[str, Sequence[str], None] = '6f46407ed01e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create system_instructions table
    op.create_table(
        'system_instructions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_default', sa.Boolean(), default=False, nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    # Create indexes
    op.create_index('ix_system_instructions_user_id', 'system_instructions', ['user_id'])
    op.create_index('ix_system_instructions_last_used_at', 'system_instructions', ['last_used_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes first
    op.drop_index('ix_system_instructions_last_used_at', table_name='system_instructions')
    op.drop_index('ix_system_instructions_user_id', table_name='system_instructions')
    # Drop table
    op.drop_table('system_instructions')

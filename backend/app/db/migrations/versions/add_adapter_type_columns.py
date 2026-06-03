"""Add adapter_type and update model_configs schema

Revision ID: add_adapter_type_001
Revises: 6f46407ed01e
Create Date: 2026-01-23 18:57:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_adapter_type_001'
down_revision: Union[str, Sequence[str], None] = '1512a097c182'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add adapter_type column to model_configs
    # Default to 'official' for existing records
    with op.batch_alter_table('model_configs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adapter_type', sa.String(length=20), nullable=True))
    
    # Update existing records to have adapter_type based on provider
    op.execute("UPDATE model_configs SET adapter_type = 'openrouter' WHERE provider = 'openrouter'")
    op.execute("UPDATE model_configs SET adapter_type = 'ollama' WHERE provider = 'ollama'")
    op.execute("UPDATE model_configs SET adapter_type = 'official' WHERE adapter_type IS NULL")
    
    # Make adapter_type not nullable after filling in values
    with op.batch_alter_table('model_configs', schema=None) as batch_op:
        batch_op.alter_column('adapter_type', nullable=False)
        # Rename api_key to encrypted_api_key
        batch_op.alter_column('api_key', new_column_name='encrypted_api_key')
        # Make provider nullable (it's only required for 'official' adapter_type)
        batch_op.alter_column('provider', type_=sa.String(50), nullable=True)
        # Make base_url nullable
        batch_op.alter_column('base_url', nullable=True)
        # Create index for adapter_type
        batch_op.create_index('ix_model_configs_adapter_type', ['adapter_type'], unique=False)

    # Update session_configs table
    with op.batch_alter_table('session_configs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('model_config_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('adapter_type', sa.String(length=20), nullable=True))
        batch_op.alter_column('model_id', nullable=True)
        batch_op.alter_column('provider', type_=sa.String(50), nullable=True)
        batch_op.create_foreign_key(
            'fk_session_configs_model_config_id',
            'model_configs',
            ['model_config_id'],
            ['id'],
            ondelete='SET NULL'
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert session_configs changes
    with op.batch_alter_table('session_configs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_session_configs_model_config_id', type_='foreignkey')
        batch_op.drop_column('adapter_type')
        batch_op.drop_column('model_config_id')
        batch_op.alter_column('model_id', nullable=False)
        batch_op.alter_column('provider', type_=sa.String(10), nullable=False)

    # Revert model_configs changes
    with op.batch_alter_table('model_configs', schema=None) as batch_op:
        batch_op.drop_index('ix_model_configs_adapter_type')
        batch_op.alter_column('encrypted_api_key', new_column_name='api_key')
        batch_op.alter_column('provider', type_=sa.String(10), nullable=False)
        batch_op.alter_column('base_url', nullable=False)
        batch_op.drop_column('adapter_type')

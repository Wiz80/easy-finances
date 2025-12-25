"""Add agent routing fields to conversation_state

Revision ID: a1b2c3d4e5f6
Revises: 5f504d1e2116
Create Date: 2025-12-03 18:00:00.000000

This migration adds fields to support the Coordinator Agent's
sticky session and handoff mechanisms:

- active_agent: Currently assigned agent (configuration, ie, coach)
- agent_locked: Whether the session is locked to the agent
- lock_reason: Why the session is locked
- lock_started_at: When the lock was acquired
- handoff_context: Data passed between agents during handoffs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '6e38192d12bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add agent routing fields to conversation_state."""
    # Add active_agent column
    op.add_column(
        'conversation_state',
        sa.Column('active_agent', sa.String(length=50), nullable=True)
    )
    
    # Add agent_locked column with default False
    op.add_column(
        'conversation_state',
        sa.Column('agent_locked', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Add lock_reason column
    op.add_column(
        'conversation_state',
        sa.Column('lock_reason', sa.String(length=100), nullable=True)
    )
    
    # Add lock_started_at column
    op.add_column(
        'conversation_state',
        sa.Column('lock_started_at', sa.DateTime(), nullable=True)
    )
    
    # Add handoff_context column (JSONB for flexible context data)
    op.add_column(
        'conversation_state',
        sa.Column(
            'handoff_context',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True
        )
    )
    
    # Create index on active_agent for faster lookups
    op.create_index(
        'ix_conversation_state_active_agent',
        'conversation_state',
        ['active_agent'],
        unique=False
    )
    
    # Create composite index for common query pattern
    op.create_index(
        'ix_conversation_state_user_agent_status',
        'conversation_state',
        ['user_id', 'active_agent', 'status'],
        unique=False
    )


def downgrade() -> None:
    """Remove agent routing fields from conversation_state."""
    # Drop indexes first
    op.drop_index('ix_conversation_state_user_agent_status', table_name='conversation_state')
    op.drop_index('ix_conversation_state_active_agent', table_name='conversation_state')
    
    # Drop columns
    op.drop_column('conversation_state', 'handoff_context')
    op.drop_column('conversation_state', 'lock_started_at')
    op.drop_column('conversation_state', 'lock_reason')
    op.drop_column('conversation_state', 'agent_locked')
    op.drop_column('conversation_state', 'active_agent')


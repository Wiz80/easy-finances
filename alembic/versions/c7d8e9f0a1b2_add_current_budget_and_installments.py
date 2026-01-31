"""Add current_budget_id to user and installment fields to expense

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-01-30 10:00:00.000000

This migration adds:
- current_budget_id to User (active budget reference, independent of trip)
- country field to User (ISO 3166-1 alpha-2)
- Installment fields to Expense (for credit card payments in installments)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add current_budget_id to user and installment fields to expense."""
    # ─────────────────────────────────────────────────────────────────────────
    # User table changes
    # ─────────────────────────────────────────────────────────────────────────
    
    # Add current_budget_id column
    op.add_column(
        'user',
        sa.Column('current_budget_id', sa.UUID(), nullable=True)
    )
    
    # Add country column (ISO 3166-1 alpha-2, e.g., "CO", "US", "MX")
    op.add_column(
        'user',
        sa.Column('country', sa.String(length=2), nullable=True)
    )
    
    # Add foreign key constraint for current_budget_id
    # Using use_alter=True to handle circular reference with budget table
    op.create_foreign_key(
        'fk_user_current_budget_id',
        'user',
        'budget',
        ['current_budget_id'],
        ['id'],
        ondelete='SET NULL',
        use_alter=True
    )
    
    # Create index for faster budget lookups
    op.create_index(
        'ix_user_current_budget_id',
        'user',
        ['current_budget_id'],
        unique=False
    )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Expense table changes - Installment support
    # ─────────────────────────────────────────────────────────────────────────
    
    # Total number of installments (e.g., "3 cuotas" = 3)
    op.add_column(
        'expense',
        sa.Column('installments_total', sa.Integer(), nullable=False, server_default='1')
    )
    
    # Number of installments already paid
    op.add_column(
        'expense',
        sa.Column('installments_paid', sa.Integer(), nullable=False, server_default='1')
    )
    
    # Amount per installment (calculated: amount_original / installments_total)
    op.add_column(
        'expense',
        sa.Column('installment_amount', sa.Numeric(precision=15, scale=2), nullable=True)
    )
    
    # Total debt amount (for tracking remaining debt on installment purchases)
    op.add_column(
        'expense',
        sa.Column('total_debt_amount', sa.Numeric(precision=15, scale=2), nullable=True)
    )
    
    # Remove server defaults after applying to existing rows
    op.alter_column('expense', 'installments_total', server_default=None)
    op.alter_column('expense', 'installments_paid', server_default=None)


def downgrade() -> None:
    """Remove current_budget_id from user and installment fields from expense."""
    # ─────────────────────────────────────────────────────────────────────────
    # Expense table - remove installment fields
    # ─────────────────────────────────────────────────────────────────────────
    op.drop_column('expense', 'total_debt_amount')
    op.drop_column('expense', 'installment_amount')
    op.drop_column('expense', 'installments_paid')
    op.drop_column('expense', 'installments_total')
    
    # ─────────────────────────────────────────────────────────────────────────
    # User table - remove budget and country fields
    # ─────────────────────────────────────────────────────────────────────────
    op.drop_index('ix_user_current_budget_id', table_name='user')
    op.drop_constraint('fk_user_current_budget_id', 'user', type_='foreignkey')
    op.drop_column('user', 'country')
    op.drop_column('user', 'current_budget_id')


"""Seed unexpected expenses category

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-01-30 10:30:00.000000

This migration adds the "Gastos Inesperados" (Unexpected Expenses) category
which is used as a fallback when expenses don't match any budget allocation.
"""
from datetime import datetime
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Fixed UUID for the unexpected category (for consistent references)
UNEXPECTED_CATEGORY_ID = 'a0000000-0000-0000-0000-000000000001'


def upgrade() -> None:
    """Insert unexpected expenses category."""
    # Define category table structure for insert
    category_table = table(
        'category',
        column('id', sa.UUID),
        column('name', sa.String),
        column('slug', sa.String),
        column('description', sa.Text),
        column('keywords', sa.Text),
        column('icon', sa.String),
        column('color', sa.String),
        column('sort_order', sa.Integer),
        column('is_active', sa.Boolean),
        column('created_at', sa.DateTime),
        column('updated_at', sa.DateTime),
    )
    
    # Insert the unexpected expenses category
    # Using ON CONFLICT DO NOTHING to handle case where it already exists
    op.execute(
        f"""
        INSERT INTO category (id, name, slug, description, keywords, icon, color, sort_order, is_active, created_at, updated_at)
        VALUES (
            '{UNEXPECTED_CATEGORY_ID}',
            'Gastos Inesperados',
            'unexpected',
            'Gastos no planificados en el presupuesto actual. Se usa cuando no hay una categoría asignada en el budget.',
            'inesperado,imprevisto,emergencia,unexpected,unplanned,emergency,extra,otros',
            '⚠️',
            '#FF9800',
            999,
            true,
            '{datetime.utcnow().isoformat()}',
            '{datetime.utcnow().isoformat()}'
        )
        ON CONFLICT (slug) DO NOTHING;
        """
    )


def downgrade() -> None:
    """Remove unexpected expenses category."""
    op.execute(
        """
        DELETE FROM category 
        WHERE slug = 'unexpected'
        """
    )


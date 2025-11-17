"""seed_categories_mvp

Revision ID: 4cffcdb68f5e
Revises: b0035a0e9246
Create Date: 2025-11-11 19:07:15.020065

"""
from datetime import datetime
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision: str = '4cffcdb68f5e'
down_revision: Union[str, Sequence[str], None] = 'b0035a0e9246'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert MVP categories."""
    # Define category table structure for bulk insert
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
    
    # MVP Categories with metadata
    categories = [
        {
            'id': uuid4(),
            'name': 'Delivery',
            'slug': 'delivery',
            'description': 'Food and goods delivery services',
            'keywords': 'delivery,uber eats,rappi,deliveroo,doordash,grubhub,pedido,entrega',
            'icon': '🚗',
            'color': '#FF6B35',
            'sort_order': 1,
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        },
        {
            'id': uuid4(),
            'name': 'In-House Food',
            'slug': 'in_house_food',
            'description': 'Groceries and food purchased for home cooking',
            'keywords': 'groceries,supermarket,market,food,ingredients,cocina,despensa,supermercado,mercado',
            'icon': '🛒',
            'color': '#4ECDC4',
            'sort_order': 2,
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        },
        {
            'id': uuid4(),
            'name': 'Out-House Food',
            'slug': 'out_house_food',
            'description': 'Dining at restaurants, cafes, and bars',
            'keywords': 'restaurant,cafe,bar,dining,comida,restaurante,cena,almuerzo,desayuno',
            'icon': '🍽️',
            'color': '#FFE66D',
            'sort_order': 3,
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        },
        {
            'id': uuid4(),
            'name': 'Lodging',
            'slug': 'lodging',
            'description': 'Hotels, hostels, Airbnb, and accommodation',
            'keywords': 'hotel,hostel,airbnb,accommodation,lodging,hospedaje,alojamiento,hostal',
            'icon': '🏨',
            'color': '#A8DADC',
            'sort_order': 4,
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        },
        {
            'id': uuid4(),
            'name': 'Transport',
            'slug': 'transport',
            'description': 'Transportation costs including taxis, buses, flights, and car rentals',
            'keywords': 'taxi,uber,bus,flight,train,rental car,transport,transporte,vuelo,avion,autobus',
            'icon': '🚕',
            'color': '#457B9D',
            'sort_order': 5,
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        },
        {
            'id': uuid4(),
            'name': 'Tourism',
            'slug': 'tourism',
            'description': 'Tourist activities, tours, attractions, and entertainment',
            'keywords': 'tour,attraction,museum,activity,entertainment,turismo,museo,actividad,entretenimiento',
            'icon': '🎭',
            'color': '#E63946',
            'sort_order': 6,
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        },
        {
            'id': uuid4(),
            'name': 'Healthcare',
            'slug': 'healthcare',
            'description': 'Medical expenses, pharmacy, and healthcare services',
            'keywords': 'doctor,pharmacy,medicine,hospital,health,medico,farmacia,medicina,salud,clinica',
            'icon': '⚕️',
            'color': '#06A77D',
            'sort_order': 7,
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        },
        {
            'id': uuid4(),
            'name': 'Miscellaneous',
            'slug': 'misc',
            'description': 'Other expenses that don\'t fit into specific categories',
            'keywords': 'other,miscellaneous,misc,varios,otros,general',
            'icon': '📦',
            'color': '#6C757D',
            'sort_order': 8,
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        },
    ]
    
    # Bulk insert categories
    op.bulk_insert(category_table, categories)


def downgrade() -> None:
    """Remove MVP categories."""
    # Delete all categories by slug to ensure we only remove the ones we created
    op.execute(
        """
        DELETE FROM category 
        WHERE slug IN (
            'delivery', 'in_house_food', 'out_house_food', 
            'lodging', 'transport', 'tourism', 'healthcare', 'misc'
        )
        """
    )

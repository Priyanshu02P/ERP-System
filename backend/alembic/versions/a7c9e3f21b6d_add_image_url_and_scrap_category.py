"""add product image_url and SCRAP location category

Revision ID: a7c9e3f21b6d
Revises: f312802b145c
Create Date: 2026-07-27 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c9e3f21b6d'
down_revision: Union[str, None] = 'f312802b145c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('image_url', sa.String(length=255), nullable=True))
    # Postgres enums can't add a value inside a transactional DDL block in
    # older versions, but modern Postgres (12+) supports it directly.
    op.execute("ALTER TYPE location_category ADD VALUE IF NOT EXISTS 'SCRAP'")


def downgrade() -> None:
    # Postgres does not support removing a value from an enum type; the
    # SCRAP value is left in place on downgrade (harmless if unused).
    op.drop_column('products', 'image_url')

"""add suppliers table and product reorder fields

Revision ID: 3eb23937e4f0
Revises: a7c9e3f21b6d
Create Date: 2026-08-02 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3eb23937e4f0'
down_revision: Union[str, None] = 'a7c9e3f21b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('suppliers',
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('gstin', sa.String(length=15), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=True),
    sa.Column('contact_person', sa.String(length=100), nullable=True),
    sa.Column('phone', sa.String(length=30), nullable=True),
    sa.Column('email', sa.String(length=150), nullable=True),
    sa.Column(
        'category',
        sa.Enum(
            'STEEL', 'STAINLESS_STEEL', 'ALUMINIUM', 'HARDWARE', 'POWDER_COATING',
            'PACKAGING', 'LOGISTICS', 'CONSUMABLES', 'OTHER',
            name='supplier_category',
        ),
        nullable=False,
    ),
    sa.Column('default_payment_terms', sa.String(length=150), nullable=True),
    sa.Column('manufacturer_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['manufacturer_id'], ['manufacturers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_suppliers_code'), 'suppliers', ['code'], unique=True)

    # products: reorder threshold columns + optional preferred-supplier FK.
    # Added as separate add_column + create_foreign_key steps since these
    # columns land on an existing table (suppliers must exist first, which
    # is guaranteed by ordering within this same upgrade()).
    op.add_column('products', sa.Column('reorder_level', sa.Numeric(14, 3), nullable=True))
    op.add_column('products', sa.Column('reorder_quantity', sa.Numeric(14, 3), nullable=True))
    op.add_column('products', sa.Column('preferred_supplier_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_products_preferred_supplier_id_suppliers',
        'products', 'suppliers',
        ['preferred_supplier_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_products_preferred_supplier_id_suppliers', 'products', type_='foreignkey')
    op.drop_column('products', 'preferred_supplier_id')
    op.drop_column('products', 'reorder_quantity')
    op.drop_column('products', 'reorder_level')

    op.drop_index(op.f('ix_suppliers_code'), table_name='suppliers')
    op.drop_table('suppliers')
    op.execute("DROP TYPE IF EXISTS supplier_category")

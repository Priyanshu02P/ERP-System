"""add purchase order tables

Revision ID: b4d8e1a9f2c3
Revises: 6f1a2d9c4e57
Create Date: 2026-08-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4d8e1a9f2c3'
down_revision: Union[str, None] = '6f1a2d9c4e57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('purchase_orders',
    sa.Column('po_number', sa.String(length=30), nullable=False),
    sa.Column('quotation_id', sa.Integer(), nullable=True),
    sa.Column('pr_id', sa.Integer(), nullable=True),
    sa.Column('supplier_id', sa.Integer(), nullable=False),
    sa.Column(
        'status',
        sa.Enum(
            'DRAFT', 'SENT', 'CONFIRMED', 'PARTIALLY_RECEIVED', 'RECEIVED', 'CLOSED', 'CANCELLED',
            name='po_status',
        ),
        nullable=False,
    ),
    sa.Column('order_date', sa.Date(), nullable=False),
    sa.Column('expected_delivery_date', sa.Date(), nullable=True),
    sa.Column('payment_terms', sa.String(length=150), nullable=True),
    sa.Column('subtotal', sa.Numeric(14, 2), nullable=False),
    sa.Column('gst_amount', sa.Numeric(14, 2), nullable=False),
    sa.Column('total_amount', sa.Numeric(14, 2), nullable=False),
    sa.Column('approved_by', sa.String(length=100), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancelled_by', sa.String(length=100), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancellation_reason', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['quotation_id'], ['vendor_quotations.id'], ),
    sa.ForeignKeyConstraint(['pr_id'], ['purchase_requisitions.id'], ),
    sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('quotation_id'),
    )
    op.create_index(op.f('ix_purchase_orders_po_number'), 'purchase_orders', ['po_number'], unique=True)

    op.create_table('purchase_order_items',
    sa.Column('po_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
    sa.Column('rate', sa.Numeric(14, 2), nullable=False),
    sa.Column('gst_rate', sa.Numeric(5, 2), nullable=True),
    sa.Column('amount', sa.Numeric(14, 2), nullable=False),
    sa.Column('received_quantity', sa.Numeric(14, 3), nullable=False),
    sa.Column(
        'line_status',
        sa.Enum('PENDING', 'PARTIAL', 'COMPLETE', name='po_line_status'),
        nullable=False,
    ),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('purchase_order_items')
    op.execute("DROP TYPE IF EXISTS po_line_status")

    op.drop_index(op.f('ix_purchase_orders_po_number'), table_name='purchase_orders')
    op.drop_table('purchase_orders')
    op.execute("DROP TYPE IF EXISTS po_status")

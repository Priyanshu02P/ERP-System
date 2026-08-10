"""add vendor invoice tables

Revision ID: 7a2e2f74aa57
Revises: cf937838efc5
Create Date: 2026-08-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a2e2f74aa57'
down_revision: Union[str, None] = 'cf937838efc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('vendor_invoices',
    sa.Column('vendor_invoice_no', sa.String(length=50), nullable=True),
    sa.Column('supplier_id', sa.Integer(), nullable=False),
    sa.Column('po_id', sa.Integer(), nullable=False),
    sa.Column('grn_id', sa.Integer(), nullable=True),
    sa.Column('invoice_date', sa.Date(), nullable=True),
    sa.Column('subtotal', sa.Numeric(14, 2), nullable=False),
    sa.Column('gst_amount', sa.Numeric(14, 2), nullable=False),
    sa.Column('total_amount', sa.Numeric(14, 2), nullable=False),
    sa.Column(
        'status',
        sa.Enum(
            'PENDING_MATCH', 'MATCHED', 'MISMATCH', 'APPROVED_FOR_PAYMENT', 'PAID', 'DISPUTED',
            name='invoice_status',
        ),
        nullable=False,
    ),
    sa.Column(
        'source',
        sa.Enum(
            'MANUAL', 'WHATSAPP_BOT', 'TELEGRAM_BOT', 'EMAIL_PARSER', 'OCR_BOT', 'API', 'AUTO_REORDER',
            name='invoice_source_channel',
        ),
        nullable=False,
    ),
    sa.Column('source_confidence', sa.Float(), nullable=True),
    sa.Column('raw_document_url', sa.String(length=500), nullable=True),
    sa.Column('match_report', sa.JSON(), nullable=True),
    sa.Column('matched_by', sa.String(length=100), nullable=True),
    sa.Column('matched_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('approved_by', sa.String(length=100), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('paid_by', sa.String(length=100), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
    sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.id'], ),
    sa.ForeignKeyConstraint(['grn_id'], ['goods_receipts.id'], ),
    sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('vendor_invoice_items',
    sa.Column('invoice_id', sa.Integer(), nullable=False),
    sa.Column('po_item_id', sa.Integer(), nullable=True),
    sa.Column('description', sa.String(length=255), nullable=False),
    sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
    sa.Column('rate', sa.Numeric(14, 2), nullable=False),
    sa.Column('gst_rate', sa.Numeric(5, 2), nullable=True),
    sa.Column('amount', sa.Numeric(14, 2), nullable=False),
    sa.Column('match_confidence', sa.Float(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['invoice_id'], ['vendor_invoices.id'], ),
    sa.ForeignKeyConstraint(['po_item_id'], ['purchase_order_items.id'], ),
    sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('vendor_invoice_items')

    op.drop_table('vendor_invoices')
    op.execute("DROP TYPE IF EXISTS invoice_status")
    op.execute("DROP TYPE IF EXISTS invoice_source_channel")

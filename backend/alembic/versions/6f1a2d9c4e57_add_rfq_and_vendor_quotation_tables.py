"""add rfq and vendor quotation tables

Revision ID: 6f1a2d9c4e57
Revises: 590830d22a78
Create Date: 2026-08-03 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f1a2d9c4e57'
down_revision: Union[str, None] = '590830d22a78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('rfqs',
    sa.Column('rfq_number', sa.String(length=30), nullable=False),
    sa.Column('pr_id', sa.Integer(), nullable=True),
    sa.Column(
        'status',
        sa.Enum('DRAFT', 'SENT', 'RESPONSES_RECEIVED', 'CLOSED', 'CANCELLED', name='rfq_status'),
        nullable=False,
    ),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('delivery_location', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['pr_id'], ['purchase_requisitions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rfqs_rfq_number'), 'rfqs', ['rfq_number'], unique=True)

    op.create_table('rfq_items',
    sa.Column('rfq_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
    sa.Column('required_delivery_date', sa.Date(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['rfq_id'], ['rfqs.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('rfq_suppliers',
    sa.Column('rfq_id', sa.Integer(), nullable=False),
    sa.Column('supplier_id', sa.Integer(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        'sent_channel',
        sa.Enum('EMAIL', 'WHATSAPP', 'TELEGRAM', 'API', name='send_channel'),
        nullable=True,
    ),
    sa.Column(
        'response_status',
        sa.Enum('SENT', 'RESPONDED', 'NO_RESPONSE', name='rfq_response_status'),
        nullable=False,
    ),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['rfq_id'], ['rfqs.id'], ),
    sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Deliberately a separate Postgres enum type from the PR module's
    # 'source_channel' (see app/db/models/vendor_quotation.py) so this
    # migration can introduce OCR_BOT without an ALTER TYPE ... ADD VALUE
    # (which Postgres won't let you use in the same transaction it runs in).
    op.create_table('vendor_quotations',
    sa.Column('rfq_id', sa.Integer(), nullable=True),
    sa.Column('supplier_id', sa.Integer(), nullable=False),
    sa.Column('vendor_quotation_no', sa.String(length=50), nullable=True),
    sa.Column('quotation_date', sa.Date(), nullable=True),
    sa.Column('validity_date', sa.Date(), nullable=True),
    sa.Column('payment_terms', sa.String(length=150), nullable=True),
    sa.Column('delivery_lead_time_days', sa.Integer(), nullable=True),
    sa.Column(
        'status',
        sa.Enum('PENDING_REVIEW', 'REVIEWED', 'SELECTED', 'REJECTED', 'EXPIRED', name='quotation_status'),
        nullable=False,
    ),
    sa.Column(
        'source',
        sa.Enum(
            'MANUAL', 'WHATSAPP_BOT', 'TELEGRAM_BOT', 'EMAIL_PARSER', 'OCR_BOT', 'API', 'AUTO_REORDER',
            name='quotation_source_channel',
        ),
        nullable=False,
    ),
    sa.Column('source_confidence', sa.Float(), nullable=True),
    sa.Column('raw_document_url', sa.String(length=500), nullable=True),
    sa.Column('reviewed_by', sa.String(length=100), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejected_by', sa.String(length=100), nullable=True),
    sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejection_reason', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['rfq_id'], ['rfqs.id'], ),
    sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('quotation_items',
    sa.Column('quotation_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=True),
    sa.Column('raw_description', sa.String(length=255), nullable=False),
    sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
    sa.Column('rate', sa.Numeric(14, 2), nullable=False),
    sa.Column('gst_rate', sa.Numeric(5, 2), nullable=True),
    sa.Column('amount', sa.Numeric(14, 2), nullable=False),
    sa.Column('match_confidence', sa.Float(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['quotation_id'], ['vendor_quotations.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('quotation_items')

    op.drop_table('vendor_quotations')
    op.execute("DROP TYPE IF EXISTS quotation_source_channel")
    op.execute("DROP TYPE IF EXISTS quotation_status")

    op.drop_table('rfq_suppliers')
    op.execute("DROP TYPE IF EXISTS rfq_response_status")
    op.execute("DROP TYPE IF EXISTS send_channel")

    op.drop_table('rfq_items')

    op.drop_index(op.f('ix_rfqs_rfq_number'), table_name='rfqs')
    op.drop_table('rfqs')
    op.execute("DROP TYPE IF EXISTS rfq_status")

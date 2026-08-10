"""add grn and qc tables

Revision ID: cf937838efc5
Revises: b4d8e1a9f2c3
Create Date: 2026-08-03 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf937838efc5'
down_revision: Union[str, None] = 'b4d8e1a9f2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('goods_receipts',
    sa.Column('grn_number', sa.String(length=30), nullable=False),
    sa.Column('po_id', sa.Integer(), nullable=False),
    sa.Column('vendor_invoice_ref', sa.String(length=100), nullable=True),
    sa.Column('vehicle_number', sa.String(length=30), nullable=True),
    sa.Column('received_by', sa.String(length=100), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        'status',
        sa.Enum('PENDING_QC', 'QC_IN_PROGRESS', 'CLOSED', name='grn_status'),
        nullable=False,
    ),
    sa.Column('overall_condition', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.id'], ),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_goods_receipts_grn_number'), 'goods_receipts', ['grn_number'], unique=True)

    op.create_table('goods_receipt_items',
    sa.Column('grn_id', sa.Integer(), nullable=False),
    sa.Column('po_item_id', sa.Integer(), nullable=False),
    sa.Column('received_quantity', sa.Numeric(14, 3), nullable=False),
    sa.Column('variance_quantity', sa.Numeric(14, 3), nullable=False),
    sa.Column('vendor_batch_number', sa.String(length=50), nullable=True),
    sa.Column('manufacturing_date', sa.Date(), nullable=True),
    sa.Column('remarks', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['grn_id'], ['goods_receipts.id'], ),
    sa.ForeignKeyConstraint(['po_item_id'], ['purchase_order_items.id'], ),
    sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('quality_inspections',
    sa.Column('qc_number', sa.String(length=30), nullable=False),
    sa.Column('grn_id', sa.Integer(), nullable=False),
    sa.Column('inspector', sa.String(length=100), nullable=False),
    sa.Column('inspected_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        'overall_disposition',
        sa.Enum('ACCEPTED', 'ACCEPTED_WITH_DEVIATION', 'REJECTED', 'PARTIAL', name='qc_disposition'),
        nullable=False,
    ),
    sa.Column('deviation_approved_by', sa.String(length=100), nullable=True),
    sa.Column('deviation_approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['grn_id'], ['goods_receipts.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('grn_id'),
    )
    op.create_index(op.f('ix_quality_inspections_qc_number'), 'quality_inspections', ['qc_number'], unique=True)

    op.create_table('quality_inspection_items',
    sa.Column('qc_id', sa.Integer(), nullable=False),
    sa.Column('grn_item_id', sa.Integer(), nullable=False),
    sa.Column('parameter_results', sa.JSON(), nullable=True),
    sa.Column(
        'disposition',
        sa.Enum('ACCEPT', 'REJECT', 'DEVIATION', name='qc_item_disposition'),
        nullable=False,
    ),
    sa.Column('accepted_quantity', sa.Numeric(14, 3), nullable=False),
    sa.Column('rejected_quantity', sa.Numeric(14, 3), nullable=False),
    sa.Column('putaway_location_id', sa.Integer(), nullable=True),
    sa.Column('manufacturer_id', sa.Integer(), nullable=True),
    sa.Column('inventory_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['qc_id'], ['quality_inspections.id'], ),
    sa.ForeignKeyConstraint(['grn_item_id'], ['goods_receipt_items.id'], ),
    sa.ForeignKeyConstraint(['putaway_location_id'], ['locations.id'], ),
    sa.ForeignKeyConstraint(['manufacturer_id'], ['manufacturers.id'], ),
    sa.ForeignKeyConstraint(['inventory_id'], ['inventories.id'], ),
    sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('quality_inspection_items')
    op.execute("DROP TYPE IF EXISTS qc_item_disposition")

    op.drop_index(op.f('ix_quality_inspections_qc_number'), table_name='quality_inspections')
    op.drop_table('quality_inspections')
    op.execute("DROP TYPE IF EXISTS qc_disposition")

    op.drop_table('goods_receipt_items')

    op.drop_index(op.f('ix_goods_receipts_grn_number'), table_name='goods_receipts')
    op.drop_table('goods_receipts')
    op.execute("DROP TYPE IF EXISTS grn_status")

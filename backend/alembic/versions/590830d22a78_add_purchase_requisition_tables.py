"""add purchase requisition tables

Revision ID: 590830d22a78
Revises: 3eb23937e4f0
Create Date: 2026-08-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '590830d22a78'
down_revision: Union[str, None] = '3eb23937e4f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('purchase_requisitions',
    sa.Column('pr_number', sa.String(length=30), nullable=False),
    sa.Column(
        'status',
        sa.Enum(
            'DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'CONVERTED', 'CLOSED',
            name='pr_status',
        ),
        nullable=False,
    ),
    sa.Column(
        'priority',
        sa.Enum('NORMAL', 'URGENT', name='pr_priority'),
        nullable=False,
    ),
    sa.Column('department', sa.String(length=100), nullable=False),
    sa.Column('raised_by', sa.String(length=100), nullable=False),
    sa.Column('required_by_date', sa.Date(), nullable=False),
    sa.Column('reason', sa.String(length=255), nullable=True),
    sa.Column('linked_sales_order', sa.String(length=50), nullable=True),
    sa.Column(
        'source',
        sa.Enum(
            'MANUAL', 'WHATSAPP_BOT', 'TELEGRAM_BOT', 'EMAIL_PARSER', 'API', 'AUTO_REORDER',
            name='source_channel',
        ),
        nullable=False,
    ),
    sa.Column('approved_by', sa.String(length=100), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejected_by', sa.String(length=100), nullable=True),
    sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejection_reason', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_requisitions_pr_number'), 'purchase_requisitions', ['pr_number'], unique=True)

    op.create_table('purchase_requisition_items',
    sa.Column('pr_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
    sa.Column('current_stock_snapshot', sa.Numeric(14, 3), nullable=True),
    sa.Column('notes', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['pr_id'], ['purchase_requisitions.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('purchase_requisition_items')

    op.drop_index(op.f('ix_purchase_requisitions_pr_number'), table_name='purchase_requisitions')
    op.drop_table('purchase_requisitions')
    op.execute("DROP TYPE IF EXISTS source_channel")
    op.execute("DROP TYPE IF EXISTS pr_priority")
    op.execute("DROP TYPE IF EXISTS pr_status")

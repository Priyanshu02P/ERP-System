"""
Import every model here so that:
  1. `Base.metadata` is aware of all tables (needed for Alembic autogenerate
     and for `Base.metadata.create_all()`), and
  2. string-based relationship references (e.g. "Product") resolve correctly.
"""

from app.db.models.unit import Unit
from app.db.models.manufacturer import Manufacturer
from app.db.models.supplier import Supplier
from app.db.models.product import Product
from app.db.models.warehouse import Warehouse
from app.db.models.rack import Rack
from app.db.models.shelf import Shelf
from app.db.models.bin import Bin
from app.db.models.location import Location
from app.db.models.inventory import Inventory
from app.db.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionItem
from app.db.models.rfq import RFQ, RFQItem, RFQSupplier
from app.db.models.vendor_quotation import VendorQuotation, QuotationItem
from app.db.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.db.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.db.models.quality_inspection import QualityInspection, QualityInspectionItem
from app.db.models.vendor_invoice import VendorInvoice, VendorInvoiceItem

__all__ = [
    "Unit",
    "Manufacturer",
    "Supplier",
    "Product",
    "Warehouse",
    "Rack",
    "Shelf",
    "Bin",
    "Location",
    "Inventory",
    "PurchaseRequisition",
    "PurchaseRequisitionItem",
    "RFQ",
    "RFQItem",
    "RFQSupplier",
    "VendorQuotation",
    "QuotationItem",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "GoodsReceipt",
    "GoodsReceiptItem",
    "QualityInspection",
    "QualityInspectionItem",
    "VendorInvoice",
    "VendorInvoiceItem",
]

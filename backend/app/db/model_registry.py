"""
Import every model, from every domain, here so that:
  1. `Base.metadata` is aware of all tables (needed for Alembic autogenerate
     and for `Base.metadata.create_all()`), and
  2. string-based relationship references (e.g. "Product") resolve correctly.

Models live inside their owning domain (see app/master_data, app/procurement,
app/wms, app/quality) rather than in one flat package. This module is the
single place that pulls them all together for SQLAlchemy's benefit; domain
code itself never needs to import from here.
"""

from app.master_data.unit.models import Unit
from app.master_data.manufacturer.models import Manufacturer
from app.master_data.product.models import Product

from app.procurement.supplier.models import Supplier
from app.procurement.requisition.models import PurchaseRequisition, PurchaseRequisitionItem
from app.procurement.rfq.models import RFQ, RFQItem, RFQSupplier
from app.procurement.vendor_quotation.models import VendorQuotation, QuotationItem
from app.procurement.purchase_order.models import PurchaseOrder, PurchaseOrderItem
from app.procurement.vendor_invoice.models import VendorInvoice, VendorInvoiceItem

from app.wms.warehouse_structure.models.warehouse import Warehouse
from app.wms.warehouse_structure.models.rack import Rack
from app.wms.warehouse_structure.models.shelf import Shelf
from app.wms.warehouse_structure.models.bin import Bin
from app.wms.warehouse_structure.models.location import Location
from app.wms.inventory.models import Inventory
from app.wms.goods_receipt.models import GoodsReceipt, GoodsReceiptItem

from app.quality.inspection.models import QualityInspection, QualityInspectionItem

__all__ = [
    "Unit",
    "Manufacturer",
    "Product",
    "Supplier",
    "PurchaseRequisition",
    "PurchaseRequisitionItem",
    "RFQ",
    "RFQItem",
    "RFQSupplier",
    "VendorQuotation",
    "QuotationItem",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "VendorInvoice",
    "VendorInvoiceItem",
    "Warehouse",
    "Rack",
    "Shelf",
    "Bin",
    "Location",
    "Inventory",
    "GoodsReceipt",
    "GoodsReceiptItem",
    "QualityInspection",
    "QualityInspectionItem",
]

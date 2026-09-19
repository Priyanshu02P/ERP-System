from datetime import date
from typing import List

from sqlalchemy.orm import Session

from app.quality.inspection.models import QualityInspection, QualityInspectionItem
from app.shared.enums import GRNStatus, QCDisposition, QCItemDisposition, InventoryStatus
from app.shared.mixins import utcnow
from app.quality.inspection.repository import QualityInspectionRepository
from app.wms.goods_receipt.repository import GoodsReceiptRepository
from app.wms.warehouse_structure.repository.location_repository import LocationRepository
from app.master_data.manufacturer.repository import ManufacturerRepository
from app.quality.inspection.schemas import QualityInspectionCreate, QualityInspectionItemCreate
from app.wms.inventory.schemas import InventoryCreate
from app.shared.base_service import BaseService
from app.wms.inventory.service import InventoryService
from app.shared.exceptions import ConflictError, ValidationError
from app.shared.transaction_logger import log_transaction, TransactionAction

_STOCK_DISPOSITIONS = (QCItemDisposition.ACCEPT, QCItemDisposition.DEVIATION)


class QualityInspectionService(BaseService[QualityInspection]):
    """
    QC pass over a GoodsReceipt. This is the seam described in
    Procurement_Implementation_Plan.md §4: an ACCEPTed line calls straight
    into the existing InventoryService.create_inventory() rather than a
    parallel "create stock" code path.

    DEVIATION lines follow the same trust pattern as AI-parsed quotations
    (§5, "machine/inspector flags it, a human approves"): Inventory is
    withheld until deviation_approved_by is set, either at creation time (if
    already approved) or later via approve_deviation().
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository: QualityInspectionRepository = QualityInspectionRepository(db)
        self.grn_repository = GoodsReceiptRepository(db)
        self.location_repository = LocationRepository(db)
        self.manufacturer_repository = ManufacturerRepository(db)
        self.inventory_service = InventoryService(db)
        super().__init__(self.repository, entity_name="QualityInspection")

    # ------------------------------------------------------------------ #
    # Numbering
    # ------------------------------------------------------------------ #

    def _generate_qc_number(self) -> str:
        year = date.today().year
        count = self.repository.count_for_year(year)
        return f"QC-{year}-{count + 1:05d}"

    # ------------------------------------------------------------------ #
    # Validation / resolution helpers
    # ------------------------------------------------------------------ #

    def _resolve_manufacturer_id(self, grn, explicit_manufacturer_id: int | None) -> int | None:
        if explicit_manufacturer_id is not None:
            return explicit_manufacturer_id
        supplier = grn.po.supplier
        return supplier.manufacturer_id if supplier is not None else None

    def _validate_stock_line(self, line: QualityInspectionItemCreate, manufacturer_id: int | None) -> None:
        if not line.accepted_quantity or line.accepted_quantity <= 0:
            raise ValidationError(
                "accepted_quantity must be greater than 0 for an ACCEPT or DEVIATION disposition"
            )
        if line.putaway_location_id is None:
            raise ValidationError("putaway_location_id is required for an ACCEPT or DEVIATION disposition")
        if not self.location_repository.exists(line.putaway_location_id):
            raise ValidationError(f"Location with id={line.putaway_location_id} does not exist")
        if manufacturer_id is None:
            raise ValidationError(
                "manufacturer_id could not be resolved (the PO's supplier has no linked "
                "manufacturer) - pass manufacturer_id explicitly on this line"
            )
        if not self.manufacturer_repository.exists(manufacturer_id):
            raise ValidationError(f"Manufacturer with id={manufacturer_id} does not exist")

    def _create_inventory_for_line(self, grn, grn_item, qc_item: QualityInspectionItem) -> None:
        inventory = self.inventory_service.create_inventory(
            InventoryCreate(
                product_id=grn_item.po_item.product_id,
                manufacturer_id=qc_item.manufacturer_id,
                location_id=qc_item.putaway_location_id,
                batch_number=grn_item.vendor_batch_number or f"{grn.grn_number}-{grn_item.id}",
                manufacturing_date=grn_item.manufacturing_date or date.today(),
                quantity=qc_item.accepted_quantity,
                status=InventoryStatus.OK,
            )
        )
        qc_item.inventory_id = inventory.id

    @staticmethod
    def _resolve_overall_disposition(dispositions: List[QCItemDisposition]) -> QCDisposition:
        values = set(dispositions)
        if values == {QCItemDisposition.ACCEPT}:
            return QCDisposition.ACCEPTED
        if values == {QCItemDisposition.REJECT}:
            return QCDisposition.REJECTED
        if QCItemDisposition.DEVIATION in values and QCItemDisposition.REJECT not in values:
            return QCDisposition.ACCEPTED_WITH_DEVIATION
        return QCDisposition.PARTIAL

    # ------------------------------------------------------------------ #
    # Creation
    # ------------------------------------------------------------------ #

    def create_qc(self, data: QualityInspectionCreate) -> QualityInspection:
        grn = self.grn_repository.get(data.grn_id)
        if grn is None:
            raise ValidationError(f"GoodsReceipt with id={data.grn_id} does not exist")
        if grn.status != GRNStatus.PENDING_QC:
            raise ConflictError(
                f"Cannot record a quality inspection against a GRN in status {grn.status.value}; "
                "it must be PENDING_QC"
            )
        if self.repository.get_by_grn(grn.id) is not None:
            raise ConflictError(f"A quality inspection has already been recorded for GRN id={grn.id}")

        grn_items_by_id = {item.id: item for item in grn.items}
        qc_items: List[QualityInspectionItem] = []
        for line in data.items:
            grn_item = grn_items_by_id.get(line.grn_item_id)
            if grn_item is None:
                raise ValidationError(
                    f"GoodsReceiptItem id={line.grn_item_id} does not belong to GRN id={grn.id}"
                )

            manufacturer_id = None
            if line.disposition in _STOCK_DISPOSITIONS:
                manufacturer_id = self._resolve_manufacturer_id(grn, line.manufacturer_id)
                self._validate_stock_line(line, manufacturer_id)

            qc_item = QualityInspectionItem(
                grn_item_id=grn_item.id,
                parameter_results=line.parameter_results,
                disposition=line.disposition,
                accepted_quantity=line.accepted_quantity or 0,
                rejected_quantity=line.rejected_quantity or 0,
                putaway_location_id=line.putaway_location_id if line.disposition in _STOCK_DISPOSITIONS else None,
                manufacturer_id=manufacturer_id,
            )

            # ACCEPT creates stock immediately. DEVIATION only does if this
            # inspection already carries an approval (data.deviation_approved_by) -
            # otherwise it waits for approve_deviation(). REJECT never does.
            if line.disposition == QCItemDisposition.ACCEPT or (
                line.disposition == QCItemDisposition.DEVIATION and data.deviation_approved_by
            ):
                self._create_inventory_for_line(grn, grn_item, qc_item)

            qc_items.append(qc_item)

        overall = self._resolve_overall_disposition([item.disposition for item in data.items])

        qc = QualityInspection(
            qc_number=self._generate_qc_number(),
            grn_id=grn.id,
            inspector=data.inspector,
            inspected_at=utcnow(),
            overall_disposition=overall,
            deviation_approved_by=data.deviation_approved_by,
            deviation_approved_at=utcnow() if data.deviation_approved_by else None,
        )
        qc.items = qc_items
        created = self.repository.create(qc)

        grn.status = GRNStatus.QC_IN_PROGRESS
        self.grn_repository.update(grn)

        log_transaction(
            TransactionAction.QC_INSPECT, "QualityInspection", created.id,
            {
                "qc_number": created.qc_number, "grn_id": grn.id, "grn_number": grn.grn_number,
                "overall_disposition": overall.value, "item_count": len(created.items),
            },
        )
        return created

    # ------------------------------------------------------------------ #
    # Deviation approval
    # ------------------------------------------------------------------ #

    def approve_deviation(self, qc_id: int, approved_by: str) -> QualityInspection:
        qc = self.get(qc_id)
        if qc.deviation_approved_by is not None:
            raise ConflictError("This quality inspection's deviation has already been approved")

        pending = [item for item in qc.items if item.disposition == QCItemDisposition.DEVIATION]
        if not pending:
            raise ConflictError("This quality inspection has no DEVIATION lines to approve")

        grn = self.grn_repository.get(qc.grn_id)
        for qc_item in pending:
            if qc_item.inventory_id is None:
                self._create_inventory_for_line(grn, qc_item.grn_item, qc_item)

        qc.deviation_approved_by = approved_by
        qc.deviation_approved_at = utcnow()
        updated = self.repository.update(qc)
        log_transaction(
            TransactionAction.QC_DEVIATION_APPROVE, "QualityInspection", qc.id,
            {"qc_number": qc.qc_number, "approved_by": approved_by, "item_count": len(pending)},
        )
        return updated

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_by_grn(self, grn_id: int) -> QualityInspection | None:
        return self.repository.get_by_grn(grn_id)

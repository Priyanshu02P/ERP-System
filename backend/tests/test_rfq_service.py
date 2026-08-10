import pytest

from app.db.schemas.unit import UnitCreate
from app.db.schemas.product import ProductCreate
from app.db.schemas.supplier import SupplierCreate
from app.db.schemas.rfq import RFQCreate, RFQItemCreate, RFQSend
from app.db.models.enums import ProductType, SupplierCategory, RFQStatus, SendChannel, RFQResponseStatus
from app.services.unit_service import UnitService
from app.services.product_service import ProductService
from app.services.supplier_service import SupplierService
from app.services.rfq_service import RFQService
from app.services.exceptions import ConflictError, ValidationError


@pytest.fixture
def product(db_session):
    unit = UnitService(db_session).create_unit(UnitCreate(code="KG", name="Kilograms"))
    return ProductService(db_session).create_product(
        ProductCreate(code="RM-CRCA-2MM", name="CRCA Sheet 2mm", product_type=ProductType.RAW, unit_id=unit.id)
    )


@pytest.fixture
def supplier(db_session):
    return SupplierService(db_session).create_supplier(
        SupplierCreate(code="SUP-TATA-DIST", name="Tata Steel Distributor", category=SupplierCategory.STEEL)
    )


@pytest.fixture
def supplier_2(db_session):
    return SupplierService(db_session).create_supplier(
        SupplierCreate(code="SUP-JSW", name="JSW Steel", category=SupplierCategory.STEEL)
    )


def _make_rfq(db_session, product, **overrides):
    payload = dict(
        due_date="2026-08-20",
        delivery_location="Apex Precision Fabricators, Plant 1",
        items=[RFQItemCreate(product_id=product.id, quantity=500)],
    )
    payload.update(overrides)
    return RFQService(db_session).create_rfq(RFQCreate(**payload))


def test_create_rfq_success(db_session, product):
    rfq = _make_rfq(db_session, product)
    assert rfq.status == RFQStatus.DRAFT
    assert rfq.rfq_number.startswith("RFQ-2026-")
    assert rfq.rfq_number.endswith("00001")
    assert len(rfq.items) == 1


def test_rfq_number_increments(db_session, product):
    rfq1 = _make_rfq(db_session, product)
    rfq2 = _make_rfq(db_session, product)
    assert rfq1.rfq_number != rfq2.rfq_number
    assert rfq2.rfq_number.endswith("00002")


def test_create_rfq_with_invalid_product_raises(db_session):
    with pytest.raises(ValidationError):
        RFQService(db_session).create_rfq(
            RFQCreate(due_date="2026-08-20", items=[RFQItemCreate(product_id=999, quantity=10)])
        )


def test_create_rfq_with_invalid_pr_raises(db_session, product):
    with pytest.raises(ValidationError):
        _make_rfq(db_session, product, pr_id=999)


def test_send_rfq_creates_supplier_links_and_transitions_status(db_session, product, supplier, supplier_2):
    service = RFQService(db_session)
    rfq = _make_rfq(db_session, product)

    sent = service.send(rfq.id, RFQSend(supplier_ids=[supplier.id, supplier_2.id], channel=SendChannel.EMAIL))
    assert sent.status == RFQStatus.SENT
    assert len(sent.suppliers) == 2
    assert all(s.response_status == RFQResponseStatus.SENT for s in sent.suppliers)
    assert all(s.sent_channel == SendChannel.EMAIL for s in sent.suppliers)
    assert all(s.sent_at is not None for s in sent.suppliers)


def test_send_rfq_only_from_draft(db_session, product, supplier):
    service = RFQService(db_session)
    rfq = _make_rfq(db_session, product)
    service.send(rfq.id, RFQSend(supplier_ids=[supplier.id]))
    with pytest.raises(ConflictError):
        service.send(rfq.id, RFQSend(supplier_ids=[supplier.id]))


def test_send_rfq_with_invalid_supplier_raises(db_session, product):
    service = RFQService(db_session)
    rfq = _make_rfq(db_session, product)
    with pytest.raises(ValidationError):
        service.send(rfq.id, RFQSend(supplier_ids=[999]))


def test_close_rfq_marks_unresponded_suppliers(db_session, product, supplier, supplier_2):
    service = RFQService(db_session)
    rfq = _make_rfq(db_session, product)
    service.send(rfq.id, RFQSend(supplier_ids=[supplier.id, supplier_2.id]))

    closed = service.close(rfq.id)
    assert closed.status == RFQStatus.CLOSED
    assert all(s.response_status == RFQResponseStatus.NO_RESPONSE for s in closed.suppliers)


def test_close_rfq_requires_sent_or_responses_received(db_session, product):
    service = RFQService(db_session)
    rfq = _make_rfq(db_session, product)
    with pytest.raises(ConflictError):
        service.close(rfq.id)


def test_mark_responded_transitions_to_responses_received(db_session, product, supplier):
    service = RFQService(db_session)
    rfq = _make_rfq(db_session, product)
    service.send(rfq.id, RFQSend(supplier_ids=[supplier.id]))

    service.mark_responded(rfq.id, supplier.id)
    refreshed = service.get(rfq.id)
    assert refreshed.status == RFQStatus.RESPONSES_RECEIVED
    link = next(s for s in refreshed.suppliers if s.supplier_id == supplier.id)
    assert link.response_status == RFQResponseStatus.RESPONDED

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.shared.enums import GRNStatus
from app.wms.goods_receipt.schemas import GoodsReceiptCreate, GoodsReceiptRead
from app.wms.goods_receipt.service import GoodsReceiptService

router = APIRouter(prefix="/goods-receipts", tags=["Goods Receipts"])


@router.post("", response_model=GoodsReceiptRead, status_code=201)
def create_grn(payload: GoodsReceiptCreate, db: Session = Depends(get_db)):
    return GoodsReceiptService(db).create_grn(payload)


@router.get("", response_model=List[GoodsReceiptRead])
def list_grns(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[GRNStatus] = None,
    po_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    service = GoodsReceiptService(db)
    if status:
        return service.get_by_status(status)
    if po_id:
        return service.get_by_po(po_id)
    return service.get_page(skip=skip, limit=limit)


@router.get("/{grn_id}", response_model=GoodsReceiptRead)
def get_grn(grn_id: int, db: Session = Depends(get_db)):
    return GoodsReceiptService(db).get(grn_id)


@router.post("/{grn_id}/close", response_model=GoodsReceiptRead)
def close_grn(grn_id: int, db: Session = Depends(get_db)):
    return GoodsReceiptService(db).close_grn(grn_id)

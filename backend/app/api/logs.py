from typing import Any, Optional

from fastapi import APIRouter, Query

from app.core.transaction_logger import read_transactions

router = APIRouter(prefix="/logs", tags=["Transaction Logs"])


@router.get("", response_model=list[dict[str, Any]])
def list_transaction_logs(
    action: Optional[str] = Query(None, description="Filter by exact action, e.g. RECEIVE, ISSUE, STATUS_CHANGE"),
    entity_id: Optional[int] = Query(None, description="Filter by inventory/entity id"),
    search: Optional[str] = Query(None, description="Free-text search across the log entry"),
    limit: int = Query(200, ge=1, le=2000),
):
    """
    Returns business transaction log entries (most recent first) from
    backend/transaction.log - i.e. RECEIVE / ISSUE / MOVE / RESERVE /
    RELEASE / STATUS_CHANGE / ADJUST / DELETE / SEED actions.
    """
    return read_transactions(action=action, entity_id=entity_id, search=search, limit=limit)

"""
Business transaction logging.

Every stock-movement action (receiving, issuing, moving, reserving,
releasing, changing status, adjusting quantity, deleting, seeding) is
recorded here as a single-line structured JSON entry, written to
``backend/transaction.log``. This is intentionally separate from normal
application/error logging (stdout / uvicorn logs) - it is a business
audit trail, not a debug log.

Each line is a standalone JSON object with the shape:

    {
        "timestamp": "2026-07-27T10:15:00.123456+00:00",
        "action": "RECEIVE",
        "entity": "Inventory",
        "entity_id": 12,
        "details": { ... action-specific fields ... }
    }

Reading it back (e.g. for a UI activity feed) means reading the file
and parsing one JSON object per line - see app/api/logs.py.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class TransactionAction:
    """Enumerates the business actions that get written to transaction.log."""

    RECEIVE = "RECEIVE"            # New stock record creation
    ISSUE = "ISSUE"                # Consumption / shipping of stock
    MOVE = "MOVE"                  # Location transfer
    RESERVE = "RESERVE"            # Stock reservation
    RELEASE = "RELEASE"            # Release of reserved stock
    STATUS_CHANGE = "STATUS_CHANGE"  # Changing status (OK, HLD, DMG, RJC, MIS, RET)
    ADJUST = "ADJUST"              # Quantity correction
    DELETE = "DELETE"              # Inventory deletion
    SEED = "SEED"                  # Initial seed execution

    # Procurement - Purchase Requisition
    PR_CREATE = "PR_CREATE"
    PR_ITEM_ADD = "PR_ITEM_ADD"
    PR_ITEM_REMOVE = "PR_ITEM_REMOVE"
    PR_SUBMIT = "PR_SUBMIT"
    PR_APPROVE = "PR_APPROVE"
    PR_REJECT = "PR_REJECT"
    PR_DELETE = "PR_DELETE"

    # Procurement - RFQ
    RFQ_CREATE = "RFQ_CREATE"
    RFQ_SEND = "RFQ_SEND"
    RFQ_CLOSE = "RFQ_CLOSE"

    # Procurement - Vendor Quotation
    QUOTATION_CREATE = "QUOTATION_CREATE"
    QUOTATION_INGEST = "QUOTATION_INGEST"
    QUOTATION_ITEM_UPDATE = "QUOTATION_ITEM_UPDATE"
    QUOTATION_REVIEW = "QUOTATION_REVIEW"
    QUOTATION_SELECT = "QUOTATION_SELECT"
    QUOTATION_REJECT = "QUOTATION_REJECT"

    # Procurement - Purchase Order
    PO_CREATE = "PO_CREATE"
    PO_UPDATE = "PO_UPDATE"
    PO_SEND = "PO_SEND"
    PO_CONFIRM = "PO_CONFIRM"
    PO_CANCEL = "PO_CANCEL"

    # Procurement - Goods Receipt Note
    GRN_CREATE = "GRN_CREATE"
    GRN_CLOSE = "GRN_CLOSE"

    # Procurement - Quality Inspection
    QC_INSPECT = "QC_INSPECT"
    QC_DEVIATION_APPROVE = "QC_DEVIATION_APPROVE"

    # Procurement - Vendor Invoice / 3-way match
    INVOICE_CREATE = "INVOICE_CREATE"
    INVOICE_INGEST = "INVOICE_INGEST"
    INVOICE_ITEM_UPDATE = "INVOICE_ITEM_UPDATE"
    INVOICE_MATCH = "INVOICE_MATCH"
    INVOICE_APPROVE_PAYMENT = "INVOICE_APPROVE_PAYMENT"
    INVOICE_MARK_PAID = "INVOICE_MARK_PAID"


# backend/app/core/transaction_logger.py -> parents[2] == backend/
_LOG_PATH = Path(__file__).resolve().parents[2] / "transaction.log"

_lock = threading.Lock()


def _log_path() -> Path:
    return _LOG_PATH


def log_transaction(
    action: str,
    entity: str,
    entity_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """
    Append one structured JSON entry to backend/transaction.log.

    Never raises: a logging failure must not break the business
    operation it is recording. Any error is swallowed silently
    (in a real system this would fall back to app-level logging).
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "details": details or {},
    }
    try:
        with _lock:
            with open(_log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass


def read_transactions(
    action: Optional[str] = None,
    entity_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Read transaction.log back out, most-recent-first, with optional filters.

    - action: exact match against the `action` field (e.g. "ISSUE")
    - entity_id: exact match against `entity_id`
    - search: case-insensitive substring match against the whole entry
      (action, entity, and the JSON-encoded details), for free-text search
    - limit: max number of entries to return (after filtering)
    """
    path = _log_path()
    if not path.exists():
        return []

    entries: list[dict[str, Any]] = []
    with _lock:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if action and entry.get("action") != action:
            continue
        if entity_id is not None and entry.get("entity_id") != entity_id:
            continue
        if search:
            haystack = json.dumps(entry, default=str).lower()
            if search.lower() not in haystack:
                continue

        entries.append(entry)
        if len(entries) >= limit:
            break

    return entries

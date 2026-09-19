# Low-Level Design — Shared Kernel (`app/shared/`)

> Part of the module-wise low-level design set. See
> [`../../HIGH_LEVEL_ARCHITECTURE.md`](../../HIGH_LEVEL_ARCHITECTURE.md) for how this fits together,
> and [`../../BUSINESS_DECISIONS.md`](../../BUSINESS_DECISIONS.md) for the "why" behind these rules.
> Sibling modules: [master_data](../master_data/LOW_LEVEL_DESIGN.md),
> [procurement](../procurement/LOW_LEVEL_DESIGN.md), [wms](../wms/LOW_LEVEL_DESIGN.md),
> [quality](../quality/LOW_LEVEL_DESIGN.md), [platform](../platform/LOW_LEVEL_DESIGN.md).

`app/shared/` is not a business domain — it's the kernel every domain module depends on: base
classes, cross-cutting utilities, and the vocabulary of errors every service speaks. Nothing in
`app/shared/` imports from a domain package; the dependency arrow only ever points the other way.

| File | Purpose |
|---|---|
| `enums.py` | Every `str, enum.Enum` shared across domains (`ProductType`, `InventoryStatus`, `POStatus`, `PRStatus`, `RFQStatus`, `QuotationStatus`, `InvoiceStatus`, `GRNStatus`, `QCDisposition`, `SupplierCategory`, `LocationCategory`, `SourceChannel`, ...) |
| `mixins.py` | `IDMixin`, `TimestampMixin`, `ActiveMixin` — give every model `id`/`created_at`/`updated_at`/`is_active` for free |
| `schemas_common.py` | Shared Pydantic base classes (e.g. `ORMBase`) reused by every domain's `schemas.py` |
| `base_repository.py` | `BaseRepository[ModelType]` |
| `base_service.py` | `BaseService[ModelType]` |
| `exceptions.py` | `ServiceError`, `NotFoundError`, `ConflictError`, `ValidationError`, `ReferencedEntityError` |
| `fuzzy_match.py` | Stdlib-only fuzzy text matcher used by the review-queue pattern |
| `transaction_logger.py` | Audit-trail writer (`log_transaction`) and reader (`read_transactions`) |
| `error_handlers.py` | Maps the four typed exceptions above to HTTP responses, registered once in `app/main.py` |

## `BaseService[ModelType]` (`base_service.py`)

Generic base every concrete service extends via `super().__init__(self.repository, entity_name=...)`.
Gives every module the same five operations for free, backed by whatever `BaseRepository` subclass the
concrete service constructs:

| Method | Purpose |
|---|---|
| `__init__(repository, entity_name="Entity")` | Stores the repository + a human-readable name used in `NotFoundError` messages |
| `get(id) -> ModelType` | Fetch by id or raise `NotFoundError(f"{entity_name} with id={id} not found")` |
| `get_all() -> List[ModelType]` | Unpaginated full list (small reference tables only) |
| `get_page(skip=0, limit=100) -> List[ModelType]` | Paginated list, used by every `GET /<resource>` list endpoint |
| `count() -> int` | Row count |
| `create(obj) -> ModelType` | Passthrough to `repository.create` |
| `update(obj) -> ModelType` | Passthrough to `repository.update` |
| `delete(id) -> None` | `get()` then `repository.delete()` — concrete services override this when a delete needs a business check first (e.g. `ReferencedEntityError`) |

## `BaseRepository[ModelType]` (`base_repository.py`)

Plain database access only — no business rules. Every concrete repository across every domain
subclasses this and adds only what its service actually needs beyond it:

`get`, `get_all`, `create`, `update`, `delete`, `exists`, `count`, `paginate`, `filter`, `bulk_create`.

## Exceptions (`exceptions.py`)

Four typed errors, all extending `ServiceError(message)`. See
`../../HIGH_LEVEL_ARCHITECTURE.md §4.1` for the HTTP status each maps to. Services never raise raw
`Exception`/`HTTPException` — this is the only vocabulary of failure the service layer speaks, which is
what lets `error_handlers.py` map them centrally instead of every router needing its own try/except.

## Fuzzy matching (`fuzzy_match.py`)

Stdlib-only (`difflib.SequenceMatcher`) first-pass text matcher, shared by
`procurement/vendor_quotation/service.py` and `procurement/vendor_invoice/service.py` to route
AI-parsed lines into "confidently mapped" vs. "needs human review".

| Symbol | Purpose |
|---|---|
| `ProductMatchCandidate(id, code, name)` | One thing a free-text description could match against — reused for both Products (quotations) and PurchaseOrderItems (invoices, keyed by `po_item.id` instead of a product id) |
| `ProductMatchResult(product_id, confidence)` | The outcome — `product_id` is `None` below threshold even though `confidence` is always populated, so a review UI can show "closest guess: 0.42" |
| `best_product_match(raw_description, candidates, threshold=0.55)` | Scores `raw_description` against every candidate's `name` and `code` (best of the two), returns the single best match; `product_id` only set if `confidence >= threshold` |

## Transaction log (`transaction_logger.py`)

Writes one JSON line per business action to `backend/transaction.log`
(`log_transaction(action, entity_type, entity_id, details)`), read back via `GET /api/v1/logs`
(exposed through `app/platform/logs/api.py`). Every state-changing service method across every domain
calls this — see `TransactionAction` for the full enum of ~40 actions. This is the audit trail: who did
what, when, to which record, without needing a separate audit table per entity.

## Error handling → HTTP status codes (`error_handlers.py`)

| Exception | HTTP status | Raised when |
|---|---|---|
| `NotFoundError` | 404 | `BaseService.get()` can't find the id |
| `ValidationError` | 422 | A business rule about the *shape* of the request fails (unmapped line, missing FK, out-of-range value) |
| `ConflictError` | 409 | A business rule about *state* fails (wrong status for this transition, already-done action) |
| `ReferencedEntityError` | 409 | A delete would orphan something that still points at it |

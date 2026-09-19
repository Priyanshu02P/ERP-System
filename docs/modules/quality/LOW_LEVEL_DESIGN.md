# Low-Level Design — Quality (`app/quality/`)

> Part of the module-wise low-level design set. See
> [`../../HIGH_LEVEL_ARCHITECTURE.md`](../../HIGH_LEVEL_ARCHITECTURE.md) for how this fits together,
> and [`../../BUSINESS_DECISIONS.md`](../../BUSINESS_DECISIONS.md) for the "why" behind these rules.
> Foundations these services build on: [shared kernel](../shared/LOW_LEVEL_DESIGN.md).
> Sibling modules: [master_data](../master_data/LOW_LEVEL_DESIGN.md),
> [procurement](../procurement/LOW_LEVEL_DESIGN.md), [wms](../wms/LOW_LEVEL_DESIGN.md),
> [platform](../platform/LOW_LEVEL_DESIGN.md).
>
> Convention used throughout: **public methods are the API a router calls** (one router function → one
> service method); **`_private` / `@staticmethod` helpers** are internal building blocks a public
> method composes, never called from a router.

One subdomain, but split out as its own top-level domain (rather than nested under `wms` or
`procurement`) because it's a distinct business capability with its own approval workflow, even though
it sits physically between Goods Receipt (`wms`) and Vendor Invoice (`procurement`) in the chain.

| Subdomain | Files |
|---|---|
| `inspection/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`QualityInspectionService`), `api.py` |

## `QualityInspectionService` (`app/quality/inspection/service.py`)

QC pass over a `GoodsReceipt` (see [wms](../wms/LOW_LEVEL_DESIGN.md#goods-receipt-appwmsgoods_receipt))
— **the seam into `InventoryService`** (see [wms](../wms/LOW_LEVEL_DESIGN.md)). One GRN has at most one
`QualityInspection` (DB-unique `grn_id` + service check, same belt-and-braces pattern as
`PurchaseOrder.quotation_id`). **Header state (`QCDisposition`):** resolved automatically from line
dispositions, not set directly.

| Method | Purpose |
|---|---|
| `_generate_qc_number()` | `QC-{year}-{00001}` |
| `_resolve_manufacturer_id(grn, explicit_manufacturer_id)` | Explicit value wins; else falls back to `grn.po.supplier.manufacturer_id` |
| `_validate_stock_line(line, manufacturer_id)` | For `ACCEPT`/`DEVIATION` lines: requires `accepted_quantity > 0`, a valid `putaway_location_id`, and a resolvable `manufacturer_id` (422 if the supplier has no manufacturer link and none was passed explicitly) |
| `_create_inventory_for_line(grn, grn_item, qc_item)` | **Calls `app.wms.inventory.service.InventoryService.create_inventory()`** with `batch_number = grn_item.vendor_batch_number or f"{grn.grn_number}-{grn_item.id}"`, `manufacturing_date = grn_item.manufacturing_date or date.today()`; stamps `qc_item.inventory_id` |
| `_resolve_overall_disposition(dispositions)` *(static)* | All `ACCEPT`→`ACCEPTED`; all `REJECT`→`REJECTED`; any `DEVIATION` with no `REJECT`→`ACCEPTED_WITH_DEVIATION`; any genuine mix→`PARTIAL` |
| `create_qc(data)` | Requires GRN `PENDING_QC` and not already inspected; per line: `ACCEPT` creates `Inventory` immediately; `REJECT` never does; `DEVIATION` only creates it immediately if `data.deviation_approved_by` was already supplied (pre-approved), otherwise **withholds** it; sets `GoodsReceipt.status = QC_IN_PROGRESS`; logs `QC_INSPECT` |
| `approve_deviation(qc_id, approved_by)` | For every still-unapproved `DEVIATION` line, calls `_create_inventory_for_line` now; stamps `deviation_approved_by`/`deviation_approved_at`; blocked if already approved or if there are no `DEVIATION` lines at all; logs `QC_DEVIATION_APPROVE` |
| `get_by_grn(grn_id)` | Lookup (also used internally to enforce the one-QC-per-GRN rule) |

## Repository layer (brief)

`app/quality/inspection/repository.py` (`QualityInspectionRepository`) is a thin
`BaseRepository[ModelType]` subclass (see [shared kernel](../shared/LOW_LEVEL_DESIGN.md)) adding
`count_for_year` and `get_by_grn` beyond generic CRUD. No business rules live here — see
`QualityInspectionService` above for those.

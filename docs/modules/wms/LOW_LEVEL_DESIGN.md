# Low-Level Design — WMS (`app/wms/`)

> Part of the module-wise low-level design set. See
> [`../../HIGH_LEVEL_ARCHITECTURE.md`](../../HIGH_LEVEL_ARCHITECTURE.md) for how this fits together,
> and [`../../BUSINESS_DECISIONS.md`](../../BUSINESS_DECISIONS.md) for the "why" behind these rules.
> Foundations these services build on: [shared kernel](../shared/LOW_LEVEL_DESIGN.md).
> Sibling modules: [master_data](../master_data/LOW_LEVEL_DESIGN.md),
> [procurement](../procurement/LOW_LEVEL_DESIGN.md), [quality](../quality/LOW_LEVEL_DESIGN.md),
> [platform](../platform/LOW_LEVEL_DESIGN.md).
>
> Convention used throughout: **public methods are the API a router calls** (one router function → one
> service method); **`_private` / `@staticmethod` helpers** are internal building blocks a public
> method composes, never called from a router.

Warehouse Management: the physical storage hierarchy, the stock records that live in it, and goods
physically arriving from Procurement before Quality Inspection decides what becomes usable stock.

| Subdomain | Files |
|---|---|
| `warehouse_structure/` | `models/{warehouse,rack,shelf,bin,location}.py`, `schemas.py` (all five, already combined upstream), `repository/{...}_repository.py` (one per entity), `service/{...}_service.py` (one per entity), `api.py` (all five, combined) |
| `inventory/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`InventoryService`), `api.py` |
| `goods_receipt/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`GoodsReceiptService`), `api.py` |

## Warehouse structure (`app/wms/warehouse_structure/`)

All four container levels follow the identical "one level of the hierarchy, parent-scoped" shape:
`Warehouse → Rack → Shelf → Bin`, assembled into a `Location` by `LocationService`.

### `WarehouseService` (`service/warehouse_service.py`)
| Method | Purpose |
|---|---|
| `create(data)` | Create, rejecting duplicate `code` |
| `update(warehouse_id, data)` | Partial update |
| `delete(warehouse_id)` | Blocked if it still has racks/locations |
| `add_rack(warehouse_id, code, description=None)` | Convenience: create a `Rack` scoped to this warehouse in one call |
| `remove_rack(rack)` | Delete a rack (used by `add_rack`'s sibling cleanup paths) |

### `RackService` (`service/rack_service.py`)
| Method | Purpose |
|---|---|
| `create(data)` | Create, `warehouse_id` required |
| `delete(rack_id)` | Blocked if it still has shelves/locations |
| `add_shelf(rack_id, code)` | Convenience: create a `Shelf` scoped to this rack |
| `remove_shelf(shelf)` | Delete a shelf |

### `ShelfService` (`service/shelf_service.py`)
| Method | Purpose |
|---|---|
| `create(data)` | Create, `rack_id` required |
| `delete(shelf_id)` | Blocked if it still has bins/locations |
| `add_bin(shelf_id, code)` | Convenience: create a `Bin` scoped to this shelf |
| `remove_bin(bin_)` | Delete a bin |

### `BinService` (`service/bin_service.py`)
| Method | Purpose |
|---|---|
| `create(data)` | Create, `shelf_id` required |
| `delete(bin_id)` | Blocked if any `Location` still references it |

### `LocationService` (`service/location_service.py`)
Assembles a `Warehouse`/`Rack`/`Shelf`/`Bin` combination into one addressable `Location`, and is the
only service that knows the hierarchy's validity rules.

| Method | Purpose |
|---|---|
| `validate_hierarchy(data)` | Enforces: a rack must belong to the given warehouse; a shelf must belong to the given rack; a bin must belong to the given shelf; `SHEET`/`PIPE`/`SCRAP` categories stop at rack level (no shelf/bin); oversized items may likewise stop at rack level |
| `get_location_path(data)` | Builds the human-readable path string, e.g. `WH1-A-03-05` or `WH1-A` for a rack-level location |
| `create_location(data)` | Validates hierarchy, rejects a duplicate path, creates |
| `update_location(location_id, data)` | Re-validates hierarchy on the new combination |
| `delete_location(location_id)` | Blocked if any `Inventory` still references it |

## `InventoryService` (`app/wms/inventory/service.py`)

Owns **every** stock-movement rule. This is the service every procurement module (PR reservation, QC
acceptance) calls into rather than touching `Inventory` rows directly — see
`../../HIGH_LEVEL_ARCHITECTURE.md §5`.

| Method | Purpose |
|---|---|
| `validate_product(product_id)` / `validate_manufacturer(manufacturer_id)` / `validate_location(location_id)` | Existence checks on the three FKs a stock record needs |
| `validate_quantity(quantity)` | Rejects `<= 0` |
| `validate_inventory(data)` | Runs all of the above against an `InventoryCreate` payload |
| `get_location_display(inventory)` | Human-readable location path for a stock record (delegates to `LocationService`-equivalent logic) |
| `create_inventory(data)` | The seam: validates, creates the row, logs a `RECEIVE` transaction. **Called directly by `QualityInspectionService`** (see [quality](../quality/LOW_LEVEL_DESIGN.md)) on QC accept/approved-deviation — no parallel "create stock" path exists anywhere else in the codebase |
| `update_inventory(inventory_id, data)` | Partial update of a stock record |
| `delete_inventory(inventory_id)` | Hard delete (no downstream references to check — `Inventory` is a leaf entity) |
| `receive_stock(data)` | Thin alias for `create_inventory` used by manual "receive stock" flows outside procurement |
| `issue_stock(inventory_id, quantity)` | Decrements quantity for an outbound movement, validates sufficient quantity available |
| `move_stock(inventory_id, new_location_id)` | Alias for `change_location` |
| `reserve_stock(inventory_id, quantity)` / `release_stock(inventory_id, quantity)` | Soft-reservation counters (e.g. against a Sales Order, not yet built) without physically moving stock |
| `change_status(inventory_id, status)` | Transitions `InventoryStatus` (`OK`/`RJC`/`MIS`/`RET`/`HLD`/`DMG`) |
| `change_location(inventory_id, new_location_id)` | Validates the new location, moves the record |
| `adjust_quantity(inventory_id, quantity_delta)` | Free-form +/- adjustment (stock count corrections) |
| `get_stock(inventory_id)` | Alias for `get()` |
| `get_by_product(product_id)` / `get_by_status(status)` / `get_by_location(location_id)` / `get_by_manufacturer(manufacturer_id)` | Filtered list queries |
| `get_available_stock(product_id)` | Sum of quantity across all `OK` records for a product (reservations aside) |
| `get_total_stock(product_id)` | Sum of quantity across all records regardless of status |
| `get_batch_stock(batch_number)` | All records sharing a batch number (traceability) |

## Goods Receipt (`app/wms/goods_receipt/`)

### `GoodsReceiptService` (`service.py`)
Records goods **physically arriving** against a `CONFIRMED` PO — deliberately independent of QC.
**State machine (`GoodsReceipt`):** `PENDING_QC → QC_IN_PROGRESS → CLOSED`.

| Method | Purpose |
|---|---|
| `_generate_grn_number()` | `GRN-{year}-{00001}` |
| `create_grn(data)` | Requires PO `CONFIRMED`/`PARTIALLY_RECEIVED`; per line, computes `variance_quantity` (received vs. what was still outstanding on that PO line), **updates `PurchaseOrderItem.received_quantity`/`line_status` and rolls `PurchaseOrder.status` to `PARTIALLY_RECEIVED`/`RECEIVED` immediately** — this is the one place PO receiving state actually changes; logs `GRN_CREATE` |
| `close_grn(grn_id)` | `QC_IN_PROGRESS → CLOSED`; requires a `QualityInspection` to already exist (i.e. not still `PENDING_QC`) — see [quality](../quality/LOW_LEVEL_DESIGN.md) |
| `get_by_status(status)` / `get_by_po(po_id)` | Filtered list queries |

## Repository layer (brief)

Every repository is a thin `BaseRepository[ModelType]` subclass (see
[shared kernel](../shared/LOW_LEVEL_DESIGN.md)). Each concrete repository adds only what its service
actually needs beyond generic CRUD:

| Repository | Extra methods beyond `BaseRepository` |
|---|---|
| `warehouse_structure/repository/location_repository.py` (`LocationRepository`) | Hierarchy-path lookups used by `LocationService.validate_hierarchy` |
| `inventory/repository.py` (`InventoryRepository`) | `get_by_product`, `get_by_status`, `get_by_location`, `get_by_manufacturer`, batch/available-quantity queries, `get_available_stock_map` (single grouped query, `{product_id: available_stock}` for every product — used by `ProcurementDashboardService.get_reorder_suggestions()` to avoid an N+1 query per product) |
| `goods_receipt/repository.py` (`GoodsReceiptRepository`) | `count_for_year`, `get_by_status`, `get_by_po` |

No repository contains business rules — every conditional you see above the repository layer belongs
to the service that calls it.

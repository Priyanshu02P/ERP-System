# Low-Level Design — Master Data (`app/master_data/`)

> Part of the module-wise low-level design set. See
> [`../../HIGH_LEVEL_ARCHITECTURE.md`](../../HIGH_LEVEL_ARCHITECTURE.md) for how this fits together,
> and [`../../BUSINESS_DECISIONS.md`](../../BUSINESS_DECISIONS.md) for the "why" behind these rules.
> Foundations these services build on: [shared kernel](../shared/LOW_LEVEL_DESIGN.md).
> Sibling modules: [procurement](../procurement/LOW_LEVEL_DESIGN.md), [wms](../wms/LOW_LEVEL_DESIGN.md),
> [quality](../quality/LOW_LEVEL_DESIGN.md), [platform](../platform/LOW_LEVEL_DESIGN.md).
>
> Convention used throughout: **public methods are the API a router calls** (one router function → one
> service method); **`_private` / `@staticmethod` helpers** are internal building blocks a public
> method composes, never called from a router.

Reference data that the rest of the system (procurement, wms) points at by foreign key, but which
carries no state machine of its own — it's created once and mostly just activated/deactivated.

| Subdomain | Files |
|---|---|
| `unit/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`UnitService`), `api.py` |
| `manufacturer/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`ManufacturerService`), `api.py` |
| `product/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`ProductService`), `api.py` |

## `UnitService` (`app/master_data/unit/service.py`)

Measurement units (KG, PCS, MTR...) that every `Product` is expressed in.

| Method | Purpose |
|---|---|
| `create_unit(data)` | Create, rejecting a duplicate `code` (`ConflictError`) |
| `update_unit(unit_id, data)` | Partial update |
| `delete_unit(unit_id)` | Delete, blocked if any `Product` still references it (`ReferencedEntityError`) |
| `activate(unit_id)` / `deactivate(unit_id)` | Toggle `ActiveMixin.is_active` |

## `ManufacturerService` (`app/master_data/manufacturer/service.py`)

"Who actually made this batch of stock" — distinct from `Supplier` (who it was bought from; see
[procurement](../procurement/LOW_LEVEL_DESIGN.md)).

| Method | Purpose |
|---|---|
| `create(data)` | Create, rejecting a duplicate `code` |
| `update(manufacturer_id, data)` | Partial update |
| `delete(manufacturer_id)` | Blocked if any `Inventory`/`Supplier` still references it |
| `activate(manufacturer_id)` / `deactivate(manufacturer_id)` | Toggle active flag |
| `search(term)` | Name/code substring search, backs `?search=` on the list endpoint |

## `ProductService` (`app/master_data/product/service.py`)

Product master (`RAW`/`WIP`/`FG`), `reorder_level`/`reorder_quantity`/`preferred_supplier_id`.

| Method | Purpose |
|---|---|
| `validate_product(unit_id)` | Existence check on `unit_id` (name is a slight misnomer — validates the unit, not the product) |
| `validate_preferred_supplier(supplier_id)` | Existence check |
| `create_product(data)` | Create, rejecting duplicate `code`, validating `unit_id`/`preferred_supplier_id` |
| `update_product(product_id, data)` | Partial update, re-validates any changed FK |
| `delete_product(product_id)` | Blocked if any `Inventory` references it |
| `activate_product(product_id)` / `deactivate_product(product_id)` | Toggle active flag |
| `change_unit(product_id, unit_id)` | Dedicated unit-change endpoint (re-validates) |
| `search_products(term)` | Name/code substring search |

## Repository layer (brief)

Each repository is a thin `BaseRepository[ModelType]` subclass (see
[shared kernel](../shared/LOW_LEVEL_DESIGN.md)) — none of the three master-data repositories add
query methods beyond generic CRUD plus their service's own `search`/`code` lookups.

# Low-Level Design — Platform (`app/platform/`)

> Part of the module-wise low-level design set. See
> [`../../HIGH_LEVEL_ARCHITECTURE.md`](../../HIGH_LEVEL_ARCHITECTURE.md) for how this fits together,
> and [`../../BUSINESS_DECISIONS.md`](../../BUSINESS_DECISIONS.md) for the "why" behind these rules.
> Foundations these build on: [shared kernel](../shared/LOW_LEVEL_DESIGN.md).
> Sibling modules: [master_data](../master_data/LOW_LEVEL_DESIGN.md),
> [procurement](../procurement/LOW_LEVEL_DESIGN.md), [wms](../wms/LOW_LEVEL_DESIGN.md),
> [quality](../quality/LOW_LEVEL_DESIGN.md).

Cross-cutting *features*, as opposed to `app/shared/`'s cross-cutting *infrastructure*: these are real
HTTP-reachable capabilities, they just don't belong to a single business domain because they read or
seed data that spans every domain.

| Subdomain | Files |
|---|---|
| `search/` | `schemas.py`, `api.py` — no model/repository/service, queries domain repositories directly |
| `logs/` | `api.py` — read-only view over `app/shared/transaction_logger.py` |
| `seed/` | `service.py`, `seed_data.json` — no model/repository/api, invoked at startup / via a CLI hook |

## Search (`app/platform/search/api.py`)

Cross-domain lookup endpoint — searches across `master_data.product`, `procurement.supplier`, and
other domains' repositories in one call rather than requiring the client to hit each domain's own
`?search=` endpoint separately.

## Logs (`app/platform/logs/api.py`)

Thin read-only wrapper around `app/shared/transaction_logger.py`'s `read_transactions()`, exposed as
`GET /api/v1/logs` (`?action=`, `?entity_id=`, `?search=`, `?limit=`). See
[shared kernel](../shared/LOW_LEVEL_DESIGN.md) for how entries get written in the first place.

## Seed (`app/platform/seed/service.py`)

Not a `BaseService` subclass — a standalone loader that reads `app/platform/seed/seed_data.json`
(units, manufacturers, products, the warehouse hierarchy, and inventory records) and inserts them via
the regular services (so seeding goes through the same validation everything else does). Keeps "what
data does a fresh environment start with" out of Python code entirely — edit the JSON, not a script.

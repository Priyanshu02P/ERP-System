# n8n Workflows

Implements `docs/modules/procurement/IMPLEMENTATION_PLAN.md §6`. Every workflow here follows one rule, held to
without exception: **the only shape of "database access" a workflow ever has is an `httpRequest` node
against this application's own API.** No workflow queries Postgres directly, and (since n8n now has its
own database — see `postgres/init/01-create-n8n-db.sql`) none of them even *could* reach the
application's tables by accident.

## Files

| File | Plan §6 bullet | Trigger | Calls |
|---|---|---|---|
| `vendor-invoice-ocr-ingest.json` | 2 | Telegram (invoice photo/doc) | `POST /vendor-invoices/ingest` |
| `vendor-quotation-ocr-ingest.json` | 3 | Telegram (quotation photo/doc) | `GET /rfqs`, `POST /quotations/ingest` |
| `rfq-broadcast.json` | 4 | Schedule (poll every 5 min) | `GET /rfqs`, `GET /suppliers/{id}`, WhatsApp/Telegram/Email send |
| `po-confirmation-bot.json` | 5 | Telegram (vendor reply) | `GET /purchase-orders`, `POST /purchase-orders/{id}/confirm` |
| `reorder-digest.json` | 6 | Schedule (daily) + Telegram (reply) | `GET /procurement/reorder-suggestions`, `POST /purchase-requisitions` |

Every write these workflows trigger still goes through the normal service-layer rules — a `/confirm`
call the API would reject (wrong PO status) is rejected here too; a PR raised via the reorder digest
still starts in `DRAFT` and needs `submit()`/`approve()` like any other PR (see
`docs/BUSINESS_DECISIONS.md §1` — no auto-approval anywhere, including from automation).

## Importing

1. Open n8n (`http://localhost:5678` when running via `docker-compose.yml`, or your own instance).
2. **Workflows → Import from File** → pick one of the `.json` files here. Repeat for each.
3. Each workflow references credentials by name (`telegram_procurement_bot`,
   `telegram_vendor_bot`, `whatsapp_procurement`, `procurement_smtp`, `mistralCloudApi`) — these are
   **not** included in the export (n8n never exports secrets). Create them under **Credentials** in the
   n8n UI first, using the same names, or re-point each node at your own credential after import.
4. Leave every workflow **inactive** until its credentials are wired up — they're shipped `"active":
   false` deliberately.

## Environment variables the workflows read

Set on the `n8n` service in `docker-compose.yml` (already added there):

| Variable | Used for |
|---|---|
| `API_BASE_URL` | Base URL for every `httpRequest` node — `http://app:8000/api/v1` inside the compose network |
| `PURCHASE_MANAGER_TELEGRAM_CHAT_ID` | Where the reorder digest is sent — **not yet in `docker-compose.yml`**, add it alongside the others when you have a real chat id |

## What's deliberately *not* here

- **A workflow that calls `/goods-receipts` or `/quality-inspections`.** GRN and QC recording stay
  human actions performed through the UI/warehouse team directly against the API — there's no bot in
  the loop for "goods physically arrived" or "this passed inspection", since those are judgment calls
  made standing in front of the delivery, not something a chat message should trigger.
- **Anything that writes with a status the API itself wouldn't allow.** No workflow ever tries to set a
  status field directly — every write is a normal `POST`/`PUT` to an action endpoint
  (`/confirm`, `/select`, `/match`, ...), so `ConflictError`/`ValidationError` protect these workflows
  exactly as they protect a human clicking the wrong button in the UI.
- **Auth on any of this.** Matches `docs/BUSINESS_DECISIONS.md §1` — RBAC is a separate, later concern;
  nothing here assumes or blocks on it.

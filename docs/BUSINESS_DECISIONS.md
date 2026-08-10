# Business Decisions

> The "why" behind the rules encoded in `app/services/`. Organized by theme rather than by phase, since
> several decisions recur across modules. For "what does the code do", see
> [`LOW_LEVEL_SERVICE_ARCHITECTURE.md`](./LOW_LEVEL_SERVICE_ARCHITECTURE.md); for the system-wide
> picture, see [`HIGH_LEVEL_ARCHITECTURE.md`](./HIGH_LEVEL_ARCHITECTURE.md). The original phase-by-phase
> build log with full context lives in `Procurement_Implementation_Plan.md` (§9–§14) — this document is
> the distilled, theme-first reference.

---

## 1. Approval & authorization

- **Manual approve/reject only, on PR and PO.** No value-threshold auto-approval (e.g. "auto-approve PRs
  under ₹10,000") is implemented anywhere. If it's needed later, it's an additive rule inside
  `PurchaseRequisitionService.submit()`/`PurchaseOrderService.send()`, not a redesign.
- **A PO has no separate `PENDING_APPROVAL` state, unlike a PR.** `PurchaseOrderService.send()` performs
  approval and dispatch as a single atomic action (`DRAFT → SENT`, `approved_by`/`approved_at` stamped
  in the same call). Rationale: sending a PO is the moment real money and vendor commitment happen —
  splitting "approved" from "sent" would let a PO sit in an ambiguous "approved but not yet sent" state
  that has no real-world equivalent worth modelling.
- **Auth/RBAC is out of scope entirely.** Every route is open; no route assumes or blocks on an identity
  system. This was a deliberate scoping decision, not an oversight — RBAC is planned separately and
  nothing in the procurement modules should need to be redesigned when it lands. The review-queue
  pattern (§3 below) is explicitly *not* a substitute for auth: it's about data trust (was this line
  read correctly off a document?), not access control (is this caller allowed to do this?). The two
  concerns stay orthogonal so adding auth later is additive.
- **Payment approval is hard-gated on `MATCHED`.** `VendorInvoiceService.approve_payment()` raises
  `ConflictError` on anything else, including `MISMATCH` — there is deliberately no "approve anyway"
  override endpoint. Paying a mismatched invoice requires either correcting it and re-matching, or (in a
  future phase) an explicit dispute/override path — silently allowing payment past a failed match would
  defeat the entire purpose of building the match.

## 2. Supplier vs. Manufacturer

Kept **fully separate** master tables, on purpose: a `Supplier` is who you procure from (e.g. "Tata
Steel Distributor", `SupplierCategory.STEEL`); a `Manufacturer` is who actually made a given batch of
stock (e.g. "Tata Steel"). The same manufacturer's goods can arrive via several different distributors,
and the two facts serve different downstream purposes — `Supplier` drives the buy-side lifecycle
(RFQ/quotation/PO), `Manufacturer` drives batch traceability on `Inventory`. `Supplier.manufacturer_id`
is an optional link between them (used by QC to default `Inventory.manufacturer_id`), not a merge.

## 3. The review-queue pattern (data trust for automated input)

Applied identically in three places, and treated as *the* pattern to reuse for any future automation
integration point:

1. **Vendor Quotation** — `ingest()` always lands in `PENDING_REVIEW`; a human maps any unmatched
   `product_id` before `select()` will run.
2. **Vendor Invoice** — `ingest()` always lands in `PENDING_MATCH`; a human maps any unmatched
   `po_item_id` before `match()` will run. (See §7 below for why there's no separate `PENDING_REVIEW`
   value here.)
3. **QC deviation** — a `DEVIATION` line doesn't create `Inventory` until a human calls
   `approve_deviation()`. Framed differently (a disposition rather than a document-parse), but the same
   shape: an automated/preliminary judgment doesn't get trusted downstream until a human signs off.

**Rule that makes this work:** nothing downstream ever reads an unreviewed record. There's no code path
anywhere that lets a `PENDING_REVIEW` quotation become a PO, or a `PENDING_MATCH` invoice with unmapped
lines get matched, or a `DEVIATION` line's stock appear in `Inventory` before approval. The gate is
enforced once, at the one action that matters (`select()`, `match()`, `approve_deviation()`), not
scattered as ad-hoc checks across every later step.

**Why `/ingest` is a separate endpoint from human entry, not a flag on the same one:** it makes the
trust boundary visible in the API surface itself, not just in a status field a caller could construct by
hand. n8n (or any future automation) only ever calls `/ingest`-suffixed endpoints; humans (and the UI)
only ever call the plain ones. A caller can't accidentally (or deliberately) claim `PENDING_REVIEW` data
is `REVIEWED` by hitting the wrong endpoint, because the wrong endpoint requires fields (`product_id`,
`po_item_id`) that automation doesn't have yet.

## 4. GRN and QC: "physically received" vs. "usable stock"

- **A GRN records physical arrival; QC records fitness for use; only QC-accepted stock ever becomes
  `Inventory`.** These are kept as three distinct facts because they *are* three distinct facts in a
  real warehouse — a truck can arrive (GRN) carrying material that's later rejected (QC), and rejected
  material should never have been "in stock" even momentarily.
- **`PurchaseOrderItem.received_quantity`/`line_status` and `PurchaseOrder.status` roll up at GRN time,
  not QC time.** `GoodsReceiptService.create_grn()` updates them immediately, independent of whatever QC
  later decides. Rationale: "goods arrived against this PO" is true the moment they arrive, regardless of
  whether they pass inspection — a PO that received 500 units, all of which QC later rejects, is still
  correctly `RECEIVED` (the vendor delivered what was ordered; the *quality* of that delivery is a
  separate problem, tracked and financially consequential through the invoice-match step, not by
  un-receiving the PO).
- **`GoodsReceiptItem.variance_quantity` is computed relative to what was still *outstanding* on the PO
  line at the moment of that GRN** (`received_quantity − (po_item.quantity − po_item.received_quantity)`
  evaluated pre-update), not against the PO line's original full quantity. This makes the variance read
  correctly across multiple partial deliveries on the same PO line — a second GRN's variance reflects
  whether *that delivery* under/over-shot what was still expected, not a stale comparison against the
  whole order.
- **A PO can have more than one GRN** (`GoodsReceipt.po_id` is not unique) — partial deliveries are a
  normal, expected pattern, not an edge case bolted on.
- **A GRN can have at most one QualityInspection** (`QualityInspection.grn_id` is DB-unique, enforced
  with a matching service-level check for a clean error message — the same belt-and-braces pattern used
  for `PurchaseOrder.quotation_id`). One inspection event covers every line on that delivery.
- **`GoodsReceipt.status` closing is a separate, explicit step from QC being recorded**
  (`PENDING_QC → QC_IN_PROGRESS` happens automatically the moment a `QualityInspection` exists;
  `QC_IN_PROGRESS → CLOSED` requires an explicit `POST /goods-receipts/{id}/close`). This gives a
  purchase officer a deliberate checkpoint to review the QC outcome — including any still-pending
  deviation approval — before considering the delivery fully settled, rather than the system closing it
  out automatically the instant an inspector finishes typing.

## 5. QC deviation approval — the trust-gate mechanics

- **`ACCEPT` creates `Inventory` immediately. `REJECT` never does. `DEVIATION` is held.** A `DEVIATION`
  line only gets its `Inventory` record either (a) immediately, if the QC record already carries
  `deviation_approved_by` at creation time (a supervisor signed off on the spot), or (b) later, via
  `POST /quality-inspections/{id}/approve-deviation`, which is blocked if already approved or if there
  are no `DEVIATION` lines to approve.
- **`manufacturer_id` on a QC line defaults from `grn.po.supplier.manufacturer_id` but is overridable,**
  because `Inventory.manufacturer_id` is non-nullable — every unit of stock needs a manufacturer of
  record, and the supplier link is the sensible default but not always correct (a distributor might
  source a specific batch from a different manufacturer than usual).
- **Header `QCDisposition` is derived, never set directly:** all-`ACCEPT` → `ACCEPTED`; all-`REJECT` →
  `REJECTED`; any `DEVIATION` with no `REJECT` present → `ACCEPTED_WITH_DEVIATION`; any other mix →
  `PARTIAL`. This keeps the header status an honest summary of the lines rather than a second source of
  truth an inspector could set inconsistently with what they actually recorded per line.

## 6. Vendor Invoice — the 3-way match

- **Tolerance values are a deliberate simplification, not specified numerically anywhere in the original
  brief:** quantity and header-total within **2%**, rate within **1%**. Loose enough to absorb rounding
  and OCR noise, tight enough to catch a real discrepancy. Both live as named constants
  (`QUANTITY_TOLERANCE_PCT`, `RATE_TOLERANCE_PCT`) at the top of `vendor_invoice_service.py`
  specifically so they're easy to tune (or make configurable per supplier/category) without touching
  matching logic.
- **What's compared against what, per line:** invoice `quantity` vs. that PO line's
  `GoodsReceiptItem.received_quantity` **on the specific GRN the invoice is linked to** (not the PO's
  cumulative received quantity across every delivery) — an invoice bills for one delivery, so it should
  be checked against that delivery. Invoice `rate` vs. the PO's own agreed `rate` — checked against the
  PO, not the GRN, since a GRN records what arrived, never a price.
- **Header check is a sanity check, not a third re-verification of every line:** invoice `total_amount`
  (computed server-side from its own lines, exactly like `PurchaseOrder.total_amount` — never trusted
  from the client even on `ingest`) vs. `PurchaseOrder.total_amount`, at the same 2% band as quantity.
- **A line with no corresponding GRN entry fails explicitly with a stated reason**, rather than being
  silently skipped or crashing — e.g. a two-line PO where only one line was ever received; the
  unreceived line's invoice entry has nothing to check against and is flagged, not ignored.
- **`match()` is re-runnable** from either `PENDING_MATCH` or `MISMATCH` — correcting a line via
  `PUT /vendor-invoices/{id}/items/{item_id}` and calling `match()` again is the expected recovery path
  for a mismatch, not a dead end requiring a new invoice record.
- **`grn_id` auto-resolves only when unambiguous.** Both `create_manual` and `ingest` set `grn_id`
  automatically *only if exactly one `GoodsReceipt` exists for the target PO*. Multiple deliveries (an
  ambiguous case) or none yet (nothing to match against) are both left `NULL` rather than guessed —
  `match()` refuses to run at all until it's set explicitly via `PUT /vendor-invoices/{id}`. Silently
  picking one of several deliveries to match a whole invoice against is exactly the kind of judgment call
  that belongs to a human, not the matcher.
- **Ingested invoice lines are fuzzy-matched against the *target PO's own line items*, not the whole
  product catalog.** An invoice can only possibly refer to something that was actually ordered on that
  specific PO, so narrowing the candidate set both improves match quality and makes an accidental
  cross-PO mismatch structurally impossible.
- **Nothing in this module touches `Inventory`.** Stock was already created (or withheld) at QC
  acceptance in the prior phase; this module's entire responsibility is financial — is this invoice safe
  to pay.

## 7. Reconciling the plan's `InvoiceStatus` enum with its review-queue narrative

The original brief specified `InvoiceStatus` with no `PENDING_REVIEW` value (`PENDING_MATCH`, `MATCHED`,
`MISMATCH`, `APPROVED_FOR_PAYMENT`, `PAID`, `DISPUTED`), while separately stating that ingested records
"always land in `PENDING_REVIEW`" — the same phrasing used for quotations, which *does* have that value.
**Resolution:** `PENDING_MATCH` plays the review-queue role for invoices. There's no separate
"reviewed, not yet matched" state the way quotations have `REVIEWED` sitting between `PENDING_REVIEW`
and `SELECTED` — for invoices, matching itself *is* the trust gate, so both manual and ingested invoices
land in the same `PENDING_MATCH` state, and `match()` simply refuses to run while any line is still
unmapped (422), which functionally reproduces the same "can't proceed until reviewed" guarantee without
inventing a status value the brief never specified.

## 8. Numbering, provenance, and other conventions

- **Every document-like entity gets a server-generated, year-scoped number** — `PR-2026-00001`,
  `RFQ-2026-00001`, `PO-2026-00001`, `GRN-2026-00001`, `QC-2026-00001` — never accepted from the client.
  Counting existing rows matching the year prefix (`_generate_..._number()` in each service) rather than
  a separate sequence table keeps numbering self-contained per module, at the cost of a small
  (currently accepted) race window under concurrent writes — acceptable for this system's write volume.
- **`subtotal`/`gst_amount`/`total_amount` are always computed server-side from line items**, on
  `PurchaseOrder` and `VendorInvoice` alike, even when the record was ingested from an OCR-read
  document. A parsed total is never trusted as-is; it's derived the same way regardless of source, which
  also means a 3-way match's header check is comparing two numbers computed the same way rather than one
  server-computed value against one vendor-supplied one.
- **`VendorQuotation.source` and `VendorInvoice.source` back the same Python `SourceChannel` enum but
  are deliberately separate Postgres enum types** (`quotation_source_channel`,
  `invoice_source_channel`). Reusing one Postgres enum type across both would mean a value added for one
  module (e.g. `OCR_BOT` for quotations) requires an `ALTER TYPE ... ADD VALUE` that Postgres cannot run
  inside the same migration transaction that also creates the dependent table — separate types sidestep
  that entirely at the cost of one extra enum type per module.
- **Enum values with no endpoint yet are left in place deliberately, not omitted:**
  `PRStatus.CONVERTED`/`CLOSED`, `RFQStatus.CANCELLED`, `QuotationStatus.EXPIRED`,
  `POStatus.CLOSED`, `InvoiceStatus.DISPUTED`. Each is reserved for a phase/feature that hasn't been
  built yet (auto-reorder digests, an RFQ cancel action, quotation expiry sweeps, PO closing, invoice
  disputes). Including them now means the *shape* of the state machine doesn't change when that phase
  eventually adds the transition — only a new service method and API route are needed, not a schema
  migration.

## 9. Deliberately not built (scope boundaries)

Explicitly out of scope even after Dashboard/KPIs (§10) and the n8n workflows (§10) were delivered,
called out here so it reads as a decision rather than a gap:

- A `/dispute` endpoint for `InvoiceStatus.DISPUTED`.
- Any value-threshold auto-approval for PR/PO, including PRs raised by the reorder-digest workflow (see
  §10 — `source=AUTO_REORDER` records provenance only, it does not skip `submit()`/`approve()`).
- RBAC/authentication (see §1) — nothing in the dashboard or workflow endpoints assumes or blocks on it
  either.
- A Sales Order module — `PurchaseRequisition.linked_sales_order` stays a free-text field with no FK for
  this reason.
- A workflow that calls `/goods-receipts` or `/quality-inspections` — see §10.
- Caching/materializing the dashboard's KPI numbers — see §10.

## 10. Dashboard/KPIs and n8n workflows

- **`ProcurementDashboardService` is read-only and un-cached on purpose.** Every number is recomputed
  from current rows on each request — no materialized view, no scheduled snapshot, no `log_transaction`
  call (a dashboard view is a query, not a business event, unlike literally everything else in this
  codebase). Fine at this system's write volume; the first thing to reconsider if the dashboard is ever
  polled often enough for the live joins across PR/PO/GRN/Inventory to matter.
- **`reorder-suggestions` is suggest-only, deliberately, the same way ingest-review-queues are
  deliberately not auto-trusted (§3).** It never creates a `PurchaseRequisition` itself — turning a
  suggestion into a PR is always a human action (via the UI, or via the reorder-digest workflow's reply
  path), and that PR still goes through the normal `DRAFT → submit → approve` flow with no shortcut.
- **A product with no `reorder_level` configured is skipped, not treated as "stock is fine."** Absence
  of a threshold is a data-completeness gap, not a signal.
- **`overdue_deliveries` only counts POs that actually have an `expected_delivery_date`.** No date means
  nothing to be overdue against — silently defaulting to "today" or some fixed lead time would invent a
  commitment the PO never actually made.
- **The n8n ↔ app boundary is structural, not just conventional:** n8n gets its own Postgres database
  (`n8n_db`, separate from `inventory_db`) specifically so it *cannot* write to the application's tables
  even by accident — every interaction is an `httpRequest` node against the API, same as any other HTTP
  client. This was a real bug in the original `docker-compose.yml` (n8n was pointed at `inventory_db`
  itself), not a hypothetical risk being pre-empted.
- **No workflow calls `/goods-receipts` or `/quality-inspections`.** Physically receiving goods and
  passing/failing inspection are judgment calls made standing in front of a delivery — deliberately kept
  as human actions through the UI/warehouse team, not something a chat message should be able to
  trigger.
- **Every workflow write goes through a normal action endpoint, never a raw status update.** The
  PO-confirmation bot, for instance, has no status guard of its own before calling
  `POST /purchase-orders/{id}/confirm` — it relies entirely on `PurchaseOrderService.confirm()`'s own
  `SENT → CONFIRMED` enforcement (409 otherwise), the same protection a human clicking the wrong UI
  button would run into.
- **RFQ broadcast polls rather than being pushed to.** The app has no outbound-webhook mechanism (by
  design — see §1's structural n8n boundary point above), so `n8n/workflows/rfq-broadcast.json` polls
  `GET /rfqs?status=SENT` on a schedule instead. This is the correct shape given that constraint, not a
  workaround for a missing feature.

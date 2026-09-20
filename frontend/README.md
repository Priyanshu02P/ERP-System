# Frontend (React)

The UI is now a React app (Vite) instead of a single static `index.html`.

```
frontend/
  web/          ← React source (Vite project). Edit here.
  dist/         ← Built output, served by FastAPI at "/". Generated, don't edit by hand.
  assets/       ← Product images, served by FastAPI at "/assets" (unchanged).
```

## Local development (hot reload against a running API)

```bash
cd frontend/web
npm install
npm run dev        # http://localhost:5173, proxies /api/v1 and /assets to :8000
```

Run the backend separately (`uvicorn app.main:app --reload` or `docker compose up`) so the proxy has
something to talk to.

## Production build

**Via Docker (recommended):** `docker compose up --build` now builds the frontend automatically — a
`frontend-builder` service runs `npm ci && npm run build` and writes straight to `frontend/dist` before
the `app` service starts. No manual npm steps needed.

**Manually / outside Docker:**
```bash
cd frontend/web
npm run build       # writes to ../dist
```

FastAPI (`backend/app/main.py`) mounts `frontend/dist` at `/` (serving `index.html` for the app shell
and its JS/CSS under `/app/...`) and continues to mount `frontend/assets` at `/assets` for product
images, unchanged from before.

## Structure

- `src/App.jsx` — page routing (client-side state, not URL-based) + top-level providers
- `src/state/AppDataContext.jsx` — central data store (products, inventory, suppliers, PRs, RFQs, …)
  with `load*` functions, mirroring the old global `state` object and its `load*` functions
- `src/state/OverlayContext.jsx` + `src/components/ActionModal.jsx` / `DetailModal.jsx` — the generic
  confirm/approve/reject modal and record-detail modal used across every procurement page
- `src/components/LineItemsBuilder.jsx` — generic dynamic add/remove line-item row editor, used by every
  create form that needs a product/qty/rate table (PR, RFQ, Quotation, PO, GRN, QC)
- `src/pages/*.jsx` — one file per sidebar page (Dashboard, Inventory, Products, Logs, Suppliers,
  Requisitions, RFQs, Quotations, PurchaseOrders, GoodsReceipts, QualityInspections, VendorInvoices,
  ProcurementOverview, ModelDocs)
- `src/data/modelDocs.js` + `src/data/modelStats.json` — content and statistics for the Model Docs page;
  update the JSON when a model is re-run, never hand-edit numbers in the prose
- `src/utils/format.js`, `src/utils/options.js` — formatting and dropdown-option helpers
- `src/styles.css` — the original CSS, unchanged (design tokens, layout, component classes)

Cross-page hand-offs (e.g. "Create RFQ from this" on an approved requisition) are done via
`onNavigate(pageId, params)`, which the target page reads once to prefill its create form.

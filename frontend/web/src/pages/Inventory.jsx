import { forwardRef, useImperativeHandle, useMemo, useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { api } from '../api';
import { byId, fmtDate, fmtNum, todayISO, STATUS_LABEL } from '../utils/format';
import { StatusBadge, TypeBadge } from '../components/Badges';
import Modal from '../components/Modal';

const STATUS_OPTIONS = [
  ['OK', 'OK — Good'], ['HLD', 'HLD — On hold'], ['DMG', 'DMG — Damaged'],
  ['RJC', 'RJC — Rejected'], ['MIS', 'MIS — Missing'], ['RET', 'RET — Returned'],
];

const SORTERS = {
  date_loaded_desc: (a, b) => new Date(b.inv.created_at) - new Date(a.inv.created_at),
  date_loaded_asc: (a, b) => new Date(a.inv.created_at) - new Date(b.inv.created_at),
  name_asc: (a, b) => (a.product?.name || '').localeCompare(b.product?.name || ''),
  name_desc: (a, b) => (b.product?.name || '').localeCompare(a.product?.name || ''),
  qty_desc: (a, b) => b.inv.quantity - a.inv.quantity,
  qty_asc: (a, b) => a.inv.quantity - b.inv.quantity,
  avail_desc: (a, b) => b.inv.available_quantity - a.inv.available_quantity,
  avail_asc: (a, b) => a.inv.available_quantity - b.inv.available_quantity,
  mfg_date_desc: (a, b) => new Date(b.inv.manufacturing_date) - new Date(a.inv.manufacturing_date),
  mfg_date_asc: (a, b) => new Date(a.inv.manufacturing_date) - new Date(b.inv.manufacturing_date),
  status_asc: (a, b) => a.inv.status.localeCompare(b.inv.status),
};

function inventorySearchable(inv, product, manufacturer, location) {
  return [
    inv.id, product?.code, product?.name, product?.part_number,
    manufacturer?.code, manufacturer?.name, inv.batch_number,
    location?.location_code, fmtDate(inv.created_at), fmtDate(inv.manufacturing_date),
  ].filter(Boolean).join(' ').toLowerCase();
}

const Inventory = forwardRef(function Inventory(_, ref) {
  const { products, manufacturers, locations, warehouses, units, inventory, loadInventory, loadLogs } = useAppData();
  const toast = useToast();

  const [search, setSearch] = useState('');
  const [fStatus, setFStatus] = useState('');
  const [fType, setFType] = useState('');
  const [fWarehouse, setFWarehouse] = useState('');
  const [fManufacturer, setFManufacturer] = useState('');
  const [sortBy, setSortBy] = useState('date_loaded_desc');

  const [receiveOpen, setReceiveOpen] = useState(false);
  const [dispatchTarget, setDispatchTarget] = useState(null);
  const [statusTarget, setStatusTarget] = useState(null);
  const [manageTarget, setManageTarget] = useState(null);

  useImperativeHandle(ref, () => ({
    openReceive: () => setReceiveOpen(true),
  }));

  const productsById = useMemo(() => byId(products), [products]);
  const manufacturersById = useMemo(() => byId(manufacturers), [manufacturers]);
  const locationsById = useMemo(() => byId(locations), [locations]);
  const unitsById = useMemo(() => byId(units), [units]);

  let rows = inventory.map(inv => ({
    inv, product: productsById[inv.product_id],
    manufacturer: manufacturersById[inv.manufacturer_id],
    location: locationsById[inv.location_id],
  }));
  rows = rows.filter(r => {
    if (fStatus && r.inv.status !== fStatus) return false;
    if (fType && r.product?.product_type !== fType) return false;
    if (fWarehouse && String(r.location?.warehouse_id) !== fWarehouse) return false;
    if (fManufacturer && String(r.inv.manufacturer_id) !== fManufacturer) return false;
    if (search && !inventorySearchable(r.inv, r.product, r.manufacturer, r.location).includes(search.trim().toLowerCase())) return false;
    return true;
  });
  rows = [...rows].sort(SORTERS[sortBy] || (() => 0));

  const refreshAfterAction = async () => { await Promise.all([loadInventory(), loadLogs()]); };

  return (
    <section className="page active">
      <div className="page-header">
        <div>
          <h1>Inventory</h1>
          <p>Search, filter, and act on every stock record across the warehouse network.</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => loadInventory()}>⟳ Refresh</button>
          <button className="btn btn-primary" onClick={() => setReceiveOpen(true)}>+ Receive stock</button>
        </div>
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <span className="search-icon">⌕</span>
          <input type="text" placeholder="Search by product, ID, manufacturer, batch, or date loaded…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select value={fType} onChange={(e) => setFType(e.target.value)}>
          <option value="">All product types</option>
          <option value="RAW">Raw material</option>
          <option value="WIP">Work in progress</option>
          <option value="FG">Finished good</option>
        </select>
        <select value={fWarehouse} onChange={(e) => setFWarehouse(e.target.value)}>
          <option value="">All warehouses</option>
          {warehouses.map(w => <option key={w.id} value={w.id}>{w.code} — {w.name}</option>)}
        </select>
        <select value={fManufacturer} onChange={(e) => setFManufacturer(e.target.value)}>
          <option value="">All manufacturers</option>
          {manufacturers.map(m => <option key={m.id} value={m.id}>{m.code} — {m.name}</option>)}
        </select>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          <option value="date_loaded_desc">Newest loaded first</option>
          <option value="date_loaded_asc">Oldest loaded first</option>
          <option value="name_asc">Product name A–Z</option>
          <option value="name_desc">Product name Z–A</option>
          <option value="qty_desc">Quantity: high–low</option>
          <option value="qty_asc">Quantity: low–high</option>
          <option value="avail_desc">Available: high–low</option>
          <option value="avail_asc">Available: low–high</option>
          <option value="mfg_date_desc">Manufacturing date: newest</option>
          <option value="mfg_date_asc">Manufacturing date: oldest</option>
          <option value="status_asc">Status A–Z</option>
        </select>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{rows.length} of {inventory.length} records</span>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Product</th><th>Manufacturer</th><th>Batch</th><th>Location</th>
              <th>Quantity</th><th>Status</th><th>Mfg. date</th><th>Date loaded</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={9}>
                <div className="empty-state">
                  <div className="empty-icon">▦</div><p>No stock records match your filters.</p>
                  <div className="empty-sub">Try clearing the search or filters, or receive new stock.</div>
                </div>
              </td></tr>
            ) : rows.map(({ inv, product, manufacturer, location }) => {
              const unit = unitsById[product?.unit_id];
              const canDispatch = inv.available_quantity > 0;
              return (
                <tr key={inv.id}>
                  <td>
                    <div className="product-cell">
                      <img className="product-thumb" src={product?.image_url || ''} alt={product?.name || ''} onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }} />
                      <div>
                        <div className="product-name">{product?.name || 'Unknown product'}</div>
                        <div className="product-sub">{product?.code || ''}{product ? <> · <TypeBadge type={product.product_type} /></> : ''}</div>
                      </div>
                    </div>
                  </td>
                  <td>{manufacturer?.name || '—'}<div className="product-sub">{manufacturer?.code || ''}</div></td>
                  <td className="mono">{inv.batch_number}</td>
                  <td className="mono">{location?.location_code || '—'}</td>
                  <td>
                    <div className="qty-block">
                      <span className="qty-avail">{fmtNum(inv.available_quantity)} {unit?.code || ''} avail.</span>
                      <span className="qty-sub">{fmtNum(inv.quantity)} total · {fmtNum(inv.reserved_quantity)} reserved</span>
                    </div>
                  </td>
                  <td><StatusBadge status={inv.status} /></td>
                  <td className="mono">{fmtDate(inv.manufacturing_date)}</td>
                  <td className="mono">{fmtDate(inv.created_at)}</td>
                  <td>
                    <div className="cell-actions">
                      <button className="btn btn-secondary btn-sm" disabled={!canDispatch} title={canDispatch ? '' : 'No available stock'} onClick={() => setDispatchTarget({ inv, product, location })}>Dispatch</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => setStatusTarget({ inv, product, location })}>Status</button>
                      <button className="btn btn-ghost btn-sm" onClick={() => setManageTarget({ inv, product, location })}>Manage ▾</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {receiveOpen && (
        <ReceiveModal
          products={products} manufacturers={manufacturers} warehouses={warehouses} locations={locations}
          onClose={() => setReceiveOpen(false)}
          onSubmit={async (body) => {
            try {
              await api('/inventory', { method: 'POST', body: JSON.stringify(body) });
              setReceiveOpen(false); toast('Stock received.'); await refreshAfterAction();
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}

      {dispatchTarget && (
        <DispatchModal
          ctx={dispatchTarget}
          onClose={() => setDispatchTarget(null)}
          onSubmit={async (qty) => {
            try {
              await api(`/inventory/${dispatchTarget.inv.id}/issue`, { method: 'POST', body: JSON.stringify({ quantity_delta: -Math.abs(qty) }) });
              setDispatchTarget(null); toast('Stock dispatched.'); await refreshAfterAction();
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}

      {statusTarget && (
        <StatusModal
          ctx={statusTarget}
          onClose={() => setStatusTarget(null)}
          onSubmit={async (status) => {
            try {
              await api(`/inventory/${statusTarget.inv.id}/status`, { method: 'POST', body: JSON.stringify({ status }) });
              setStatusTarget(null); toast('Status updated.'); await refreshAfterAction();
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}

      {manageTarget && (
        <ManageModal
          ctx={manageTarget}
          locations={locations} warehouses={warehouses}
          onClose={() => setManageTarget(null)}
          toast={toast}
          refresh={refreshAfterAction}
        />
      )}
    </section>
  );
});

export default Inventory;

function ReceiveModal({ products, manufacturers, warehouses, locations, onClose, onSubmit }) {
  const unitsCtx = useAppData().units;
  const unitsById = useMemo(() => byId(unitsCtx), [unitsCtx]);
  const [productId, setProductId] = useState(products[0]?.id || '');
  const [manufacturerId, setManufacturerId] = useState(manufacturers[0]?.id || '');
  const [locationId, setLocationId] = useState('');
  const [batch, setBatch] = useState('');
  const [mfgDate, setMfgDate] = useState(todayISO());
  const [qty, setQty] = useState('');
  const [status, setStatus] = useState('OK');

  const submit = (e) => {
    e.preventDefault();
    onSubmit({
      product_id: Number(productId), manufacturer_id: Number(manufacturerId), location_id: Number(locationId),
      batch_number: batch, manufacturing_date: mfgDate, quantity: Number(qty), status,
    });
  };

  return (
    <Modal open onClose={onClose} title="Receive stock">
      <form onSubmit={submit}>
        <div className="form-group">
          <label>Product</label>
          <select required value={productId} onChange={(e) => setProductId(e.target.value)}>
            {products.map(p => <option key={p.id} value={p.id}>{p.code} — {p.name} ({unitsById[p.unit_id]?.code || ''})</option>)}
          </select>
        </div>
        <div className="form-row-2">
          <div className="form-group">
            <label>Manufacturer</label>
            <select required value={manufacturerId} onChange={(e) => setManufacturerId(e.target.value)}>
              {manufacturers.map(m => <option key={m.id} value={m.id}>{m.code} — {m.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Location</label>
            <select required value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              <option value="" disabled hidden>Select…</option>
              {warehouses.map(w => {
                const opts = locations.filter(l => l.warehouse_id === w.id);
                if (!opts.length) return null;
                return (
                  <optgroup key={w.id} label={`${w.code} — ${w.name}`}>
                    {opts.map(l => <option key={l.id} value={l.id}>{l.location_code} ({l.category})</option>)}
                  </optgroup>
                );
              })}
            </select>
          </div>
        </div>
        <div className="form-row-2">
          <div className="form-group">
            <label>Batch number</label>
            <input type="text" placeholder="e.g. B-ST-100" required value={batch} onChange={(e) => setBatch(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Manufacturing date</label>
            <input type="date" required max={todayISO()} value={mfgDate} onChange={(e) => setMfgDate(e.target.value)} />
          </div>
        </div>
        <div className="form-row-2">
          <div className="form-group">
            <label>Quantity</label>
            <input type="number" min="0.001" step="any" placeholder="e.g. 50" required value={qty} onChange={(e) => setQty(e.target.value)} />
          </div>
          <div className="form-group">
            <label>Status</label>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUS_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Receive stock</button>
        </div>
      </form>
    </Modal>
  );
}

function DispatchModal({ ctx, onClose, onSubmit }) {
  const [qty, setQty] = useState('');
  return (
    <Modal open onClose={onClose} title="Dispatch stock">
      <div className="modal-context">
        <div className="ctx-name">{ctx.product?.name || 'Unknown product'} · Batch {ctx.inv.batch_number}</div>
        <div className="ctx-sub">{fmtNum(ctx.inv.available_quantity)} available at {ctx.location?.location_code || '—'}</div>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(Number(qty)); }}>
        <div className="form-group">
          <label>Quantity to dispatch</label>
          <input type="number" min="0.001" step="any" max={ctx.inv.available_quantity} required value={qty} onChange={(e) => setQty(e.target.value)} />
          <div className="hint-text">Cannot exceed the available (unreserved) quantity shown above.</div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Dispatch</button>
        </div>
      </form>
    </Modal>
  );
}

function StatusModal({ ctx, onClose, onSubmit }) {
  const [status, setStatus] = useState(ctx.inv.status);
  return (
    <Modal open onClose={onClose} title="Change status">
      <div className="modal-context">
        <div className="ctx-name">{ctx.product?.name || 'Unknown product'} · Batch {ctx.inv.batch_number}</div>
        <div className="ctx-sub">Current status: {STATUS_LABEL[ctx.inv.status]}</div>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(status); }}>
        <div className="form-group">
          <label>New status</label>
          <select required value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="OK">OK — Good, ready to use</option>
            <option value="HLD">HLD — On hold</option>
            <option value="DMG">DMG — Damaged</option>
            <option value="RJC">RJC — Rejected</option>
            <option value="MIS">MIS — Missing</option>
            <option value="RET">RET — Returned</option>
          </select>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Update status</button>
        </div>
      </form>
    </Modal>
  );
}

function ManageModal({ ctx, locations, warehouses, onClose, toast, refresh }) {
  const [tab, setTab] = useState('reserve');
  const [reserveQty, setReserveQty] = useState('');
  const [releaseQty, setReleaseQty] = useState('');
  const [moveLocation, setMoveLocation] = useState(ctx.inv.location_id);
  const [adjustDelta, setAdjustDelta] = useState('');

  const run = async (path, body, successMsg) => {
    try {
      await api(`/inventory/${ctx.inv.id}/${path}`, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined });
      onClose(); toast(successMsg); await refresh();
    } catch (err) { toast(err.message, 'error'); }
  };

  const doDelete = async () => {
    if (!window.confirm('Delete this stock record? This cannot be undone.')) return;
    try {
      await api(`/inventory/${ctx.inv.id}`, { method: 'DELETE' });
      onClose(); toast('Stock record deleted.'); await refresh();
    } catch (err) { toast(err.message, 'error'); }
  };

  return (
    <Modal open onClose={onClose} title="Manage stock record">
      <div className="modal-context">
        <div className="ctx-name">{ctx.product?.name || 'Unknown product'} · Batch {ctx.inv.batch_number}</div>
        <div className="ctx-sub">{fmtNum(ctx.inv.quantity)} total · {fmtNum(ctx.inv.reserved_quantity)} reserved · {ctx.location?.location_code || '—'}</div>
      </div>
      <div className="tabs-row">
        {['reserve', 'release', 'move', 'adjust', 'delete'].map(t => (
          <button key={t} type="button" className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t === 'adjust' ? 'Adjust qty' : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'reserve' && (
        <form onSubmit={(e) => { e.preventDefault(); run('reserve', { quantity: Number(reserveQty) }, 'Stock reserved.'); }}>
          <div className="form-group">
            <label>Quantity to reserve</label>
            <input type="number" min="0.001" step="any" required value={reserveQty} onChange={(e) => setReserveQty(e.target.value)} />
            <div className="hint-text">Sets stock aside so it can't be dispatched, without moving or removing it.</div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Reserve</button>
          </div>
        </form>
      )}
      {tab === 'release' && (
        <form onSubmit={(e) => { e.preventDefault(); run('release', { quantity: Number(releaseQty) }, 'Reservation released.'); }}>
          <div className="form-group">
            <label>Quantity to release</label>
            <input type="number" min="0.001" step="any" required value={releaseQty} onChange={(e) => setReleaseQty(e.target.value)} />
            <div className="hint-text">Frees up previously reserved stock so it becomes available again.</div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Release</button>
          </div>
        </form>
      )}
      {tab === 'move' && (
        <form onSubmit={(e) => { e.preventDefault(); run('move', { new_location_id: Number(moveLocation) }, 'Stock moved.'); }}>
          <div className="form-group">
            <label>New location</label>
            <select required value={moveLocation} onChange={(e) => setMoveLocation(e.target.value)}>
              {warehouses.map(w => {
                const opts = locations.filter(l => l.warehouse_id === w.id);
                if (!opts.length) return null;
                return (
                  <optgroup key={w.id} label={`${w.code} — ${w.name}`}>
                    {opts.map(l => <option key={l.id} value={l.id}>{l.location_code} ({l.category})</option>)}
                  </optgroup>
                );
              })}
            </select>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Move</button>
          </div>
        </form>
      )}
      {tab === 'adjust' && (
        <form onSubmit={(e) => { e.preventDefault(); run('adjust', { quantity_delta: Number(adjustDelta) }, 'Quantity adjusted.'); }}>
          <div className="form-group">
            <label>Quantity change</label>
            <input type="number" step="any" required placeholder="e.g. 5 or -3" value={adjustDelta} onChange={(e) => setAdjustDelta(e.target.value)} />
            <div className="hint-text">Positive corrects stock upward (found more); negative corrects downward (found less).</div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Apply adjustment</button>
          </div>
        </form>
      )}
      {tab === 'delete' && (
        <div>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: 1.5 }}>
            This permanently deletes this stock record. This cannot be undone.
          </p>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="button" className="btn btn-danger" onClick={doDelete}>Delete stock record</button>
          </div>
        </div>
      )}
    </Modal>
  );
}

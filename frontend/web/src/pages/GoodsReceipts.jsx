import { useEffect, useMemo, useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { useOverlay } from '../state/OverlayContext';
import { api } from '../api';
import { byId, fmtDate, fmtNum, todayISO } from '../utils/format';
import { productLabel, locationOptionsFlat } from '../utils/options';
import { PBadge } from '../components/Badges';
import { DetailMeta } from '../components/DetailModal';
import Modal from '../components/Modal';
import LineItemsBuilder, { blankRow, collectRows } from '../components/LineItemsBuilder';

export default function GoodsReceipts({ onNavigate, navParams }) {
  const { goodsReceipts, purchaseOrders, suppliers, products, locations, warehouses, loadGRNs, loadPOs, loadInventory, loadLogs } = useAppData();
  const toast = useToast();
  const { openDetailModal, closeDetailModal } = useOverlay();

  const [search, setSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [prefillPoId, setPrefillPoId] = useState(null);

  useEffect(() => {
    if (navParams?.poId) { setPrefillPoId(navParams.poId); setCreateOpen(true); }
  }, [navParams]);

  const rows = goodsReceipts.filter(g => {
    if (search && !g.grn_number.toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  }).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const poById = useMemo(() => byId(purchaseOrders), [purchaseOrders]);
  const receivablePOs = purchaseOrders.filter(p => ['CONFIRMED', 'SENT', 'PARTIALLY_RECEIVED'].includes(p.status));

  const openDetail = (g) => {
    const po = poById[g.po_id];
    const itemsHtml = (
      <table className="detail-items-table">
        <thead><tr><th>Product</th><th>Ordered</th><th>Received</th><th>Batch</th></tr></thead>
        <tbody>{g.items.map((i, idx) => <tr key={idx}><td>{productLabel(products, i.product_id)}</td><td className="mono">{fmtNum(i.ordered_quantity ?? '—')}</td><td className="mono">{fmtNum(i.received_quantity)}</td><td className="mono">{i.batch_number || '—'}</td></tr>)}</tbody>
      </table>
    );
    const actions = [
      <button key="qc" className="btn btn-secondary btn-sm" onClick={() => { closeDetailModal(); onNavigate('quality-inspections', { grnId: g.id }); }}>Run quality check</button>,
    ];
    openDetailModal({
      title: `GRN ${g.grn_number}`,
      body: (
        <>
          <DetailMeta pairs={[['Purchase order', po?.po_number || '#' + g.po_id], ['Received date', fmtDate(g.received_date)], ['Received by', g.received_by || '—'], ['Status', <PBadge status={g.status} key="s" />]]} />
          <div className="detail-section-label">Line items</div>{itemsHtml}
        </>
      ),
      actions,
    });
  };

  return (
    <section className="page active">
      <div className="page-header">
        <div><h1>Goods receipts</h1><p>Record what physically arrived against a confirmed purchase order.</p></div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => loadGRNs()}>⟳ Refresh</button>
          <button className="btn btn-primary" onClick={() => { setPrefillPoId(null); setCreateOpen(true); }}>+ Log goods receipt</button>
        </div>
      </div>
      <div className="toolbar">
        <div className="search-wrap"><span className="search-icon">⌕</span>
          <input type="text" placeholder="Search by GRN number…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{rows.length} of {goodsReceipts.length} receipts</span>
      </div>
      <div className="table-container">
        <table>
          <thead><tr><th>GRN number</th><th>Purchase order</th><th>Received date</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={5}><div className="empty-state"><div className="empty-icon">⇩</div><p>No goods receipts logged yet.</p></div></td></tr>
            ) : rows.map(g => (
              <tr key={g.id}>
                <td className="mono">{g.grn_number}</td>
                <td className="mono">{poById[g.po_id]?.po_number || '#' + g.po_id}</td>
                <td className="mono">{fmtDate(g.received_date)}</td>
                <td><PBadge status={g.status} /></td>
                <td><div className="cell-actions"><button className="btn btn-ghost btn-sm" onClick={() => openDetail(g)}>View</button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {createOpen && (
        <GRNCreateModal
          purchaseOrders={receivablePOs} suppliers={suppliers} products={products}
          locations={locations} warehouses={warehouses} prefillPoId={prefillPoId}
          onClose={() => setCreateOpen(false)}
          onSubmit={async (body) => {
            try {
              await api('/goods-receipts', { method: 'POST', body: JSON.stringify(body) });
              setCreateOpen(false); toast('Goods receipt logged.');
              await Promise.all([loadGRNs(), loadPOs(), loadInventory(), loadLogs()]);
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}
    </section>
  );
}

function GRNCreateModal({ purchaseOrders, suppliers, products, locations, warehouses, prefillPoId, onClose, onSubmit }) {
  const [poId, setPoId] = useState(prefillPoId ? String(prefillPoId) : '');
  const [receivedDate, setReceivedDate] = useState(todayISO());
  const [receivedBy, setReceivedBy] = useState('');
  const [locationId, setLocationId] = useState('');
  const [rows, setRows] = useState([]);

  const po = purchaseOrders.find(p => String(p.id) === poId) || null;
  const productsById = byId(products);

  const fields = useMemo(() => ([
    { key: 'product_id', label: 'Product', type: 'select', numeric: true, options: po ? po.items.map(i => ({ value: String(i.product_id), label: productsById[i.product_id]?.name || '#' + i.product_id })) : [] },
    { key: 'received_quantity', label: 'Qty received', type: 'number', step: 'any', min: 0, numeric: true },
    { key: 'batch_number', label: 'Batch number', required: false },
    { key: 'location_id', label: 'Location', type: 'select', numeric: true, options: locationOptionsFlat(locations, warehouses) },
  ]), [po, locations, warehouses]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (po) {
      setRows(po.items.filter(i => i.line_status !== 'RECEIVED').map(i => blankRow(fields, {
        product_id: String(i.product_id), received_quantity: String(Number(i.quantity) - Number(i.received_quantity || 0)),
      })));
    } else {
      setRows([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [poId]);

  const submit = (e) => {
    e.preventDefault();
    if (!poId) return;
    const items = collectRows(rows, fields).map(i => ({
      product_id: Number(i.product_id), received_quantity: Number(i.received_quantity),
      batch_number: i.batch_number || undefined, location_id: i.location_id ? Number(i.location_id) : undefined,
    }));
    if (!items.length) return;
    onSubmit({ po_id: Number(poId), received_date: receivedDate, received_by: receivedBy || undefined, items });
  };

  return (
    <Modal open onClose={onClose} title="Log goods receipt" wide>
      <form onSubmit={submit}>
        <div className="form-row-2">
          <div className="form-group"><label>Purchase order</label>
            <select required value={poId} onChange={(e) => setPoId(e.target.value)}>
              <option value="" disabled hidden>Select…</option>
              {purchaseOrders.map(p => <option key={p.id} value={p.id}>{p.po_number} — {suppliers.find(s => s.id === p.supplier_id)?.name || ''}</option>)}
            </select>
          </div>
          <div className="form-group"><label>Received date</label><input type="date" required max={todayISO()} value={receivedDate} onChange={(e) => setReceivedDate(e.target.value)} /></div>
        </div>
        <div className="form-group"><label>Received by (optional)</label><input type="text" value={receivedBy} onChange={(e) => setReceivedBy(e.target.value)} /></div>
        <div className="form-subhead">Line items</div>
        {po ? (
          <LineItemsBuilder label="Items received" fields={fields} rows={rows} setRows={setRows} />
        ) : <div className="hint-text">Select a purchase order to load its outstanding line items.</div>}
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Log receipt</button>
        </div>
      </form>
    </Modal>
  );
}

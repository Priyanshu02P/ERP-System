import { useEffect, useMemo, useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { useOverlay } from '../state/OverlayContext';
import { api } from '../api';
import { byId, fmtDate, fmtNum, todayISO } from '../utils/format';
import { productLabel } from '../utils/options';
import { PBadge } from '../components/Badges';
import { DetailMeta } from '../components/DetailModal';
import Modal from '../components/Modal';
import LineItemsBuilder, { blankRow, collectRows } from '../components/LineItemsBuilder';

const RESULT_OPTIONS = [
  ['ACCEPTED', 'Accepted'], ['ACCEPTED_WITH_DEVIATION', 'Accepted with deviation'],
  ['REJECTED', 'Rejected'], ['PARTIAL', 'Partially accepted'],
];

export default function QualityInspections({ navParams }) {
  const { qualityInspections, goodsReceipts, products, loadQCs, loadGRNs, loadInventory, loadLogs } = useAppData();
  const toast = useToast();
  const { openDetailModal } = useOverlay();

  const [search, setSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [prefillGrnId, setPrefillGrnId] = useState(null);

  useEffect(() => {
    if (navParams?.grnId) { setPrefillGrnId(navParams.grnId); setCreateOpen(true); }
  }, [navParams]);

  const grnById = useMemo(() => byId(goodsReceipts), [goodsReceipts]);
  const rows = qualityInspections.filter(q => {
    if (search && !(grnById[q.grn_id]?.grn_number || '').toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  }).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const uninspectedGRNs = goodsReceipts.filter(g => !qualityInspections.some(q => q.grn_id === g.id));

  const openDetail = (q) => {
    const itemsHtml = (
      <table className="detail-items-table">
        <thead><tr><th>Product</th><th>Qty inspected</th><th>Accepted</th><th>Rejected</th><th>Reason</th></tr></thead>
        <tbody>{q.items.map((i, idx) => <tr key={idx}><td>{productLabel(products, i.product_id)}</td><td className="mono">{fmtNum(i.quantity_inspected)}</td><td className="mono">{fmtNum(i.quantity_accepted)}</td><td className="mono">{fmtNum(i.quantity_rejected)}</td><td>{i.rejection_reason || '—'}</td></tr>)}</tbody>
      </table>
    );
    openDetailModal({
      title: `QC — ${grnById[q.grn_id]?.grn_number || '#' + q.grn_id}`,
      body: (
        <>
          <DetailMeta pairs={[['Inspected by', q.inspected_by || '—'], ['Inspection date', fmtDate(q.inspection_date)], ['Result', <PBadge status={q.overall_result} key="s" />]]} />
          {q.notes && <div className="detail-note">{q.notes}</div>}
          <div className="detail-section-label">Line items</div>{itemsHtml}
        </>
      ),
    });
  };

  return (
    <section className="page active">
      <div className="page-header">
        <div><h1>Quality inspections</h1><p>Inspect received goods and record acceptance or rejection per line.</p></div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => loadQCs()}>⟳ Refresh</button>
          <button className="btn btn-primary" onClick={() => { setPrefillGrnId(null); setCreateOpen(true); }}>+ New inspection</button>
        </div>
      </div>
      <div className="toolbar">
        <div className="search-wrap"><span className="search-icon">⌕</span>
          <input type="text" placeholder="Search by GRN number…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{rows.length} of {qualityInspections.length} inspections</span>
      </div>
      <div className="table-container">
        <table>
          <thead><tr><th>GRN</th><th>Inspected by</th><th>Inspection date</th><th>Result</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={5}><div className="empty-state"><div className="empty-icon">✓</div><p>No quality inspections logged yet.</p></div></td></tr>
            ) : rows.map(q => (
              <tr key={q.id}>
                <td className="mono">{grnById[q.grn_id]?.grn_number || '#' + q.grn_id}</td>
                <td>{q.inspected_by || '—'}</td>
                <td className="mono">{fmtDate(q.inspection_date)}</td>
                <td><PBadge status={q.overall_result} /></td>
                <td><div className="cell-actions"><button className="btn btn-ghost btn-sm" onClick={() => openDetail(q)}>View</button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {createOpen && (
        <QCCreateModal
          goodsReceipts={uninspectedGRNs} products={products} prefillGrnId={prefillGrnId}
          onClose={() => setCreateOpen(false)}
          onSubmit={async (body) => {
            try {
              await api('/quality-inspections', { method: 'POST', body: JSON.stringify(body) });
              setCreateOpen(false); toast('Quality inspection logged.');
              await Promise.all([loadQCs(), loadGRNs(), loadInventory(), loadLogs()]);
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}
    </section>
  );
}

function QCCreateModal({ goodsReceipts, products, prefillGrnId, onClose, onSubmit }) {
  const [grnId, setGrnId] = useState(prefillGrnId ? String(prefillGrnId) : '');
  const [inspectedBy, setInspectedBy] = useState('');
  const [date, setDate] = useState(todayISO());
  const [notes, setNotes] = useState('');
  const [rows, setRows] = useState([]);
  const productsById = byId(products);

  const grn = goodsReceipts.find(g => String(g.id) === grnId) || null;

  const fields = useMemo(() => ([
    { key: 'product_id', label: 'Product', type: 'select', numeric: true, options: grn ? grn.items.map(i => ({ value: String(i.product_id), label: productsById[i.product_id]?.name || '#' + i.product_id })) : [] },
    { key: 'quantity_inspected', label: 'Qty inspected', type: 'number', step: 'any', min: 0, numeric: true },
    { key: 'quantity_accepted', label: 'Qty accepted', type: 'number', step: 'any', min: 0, numeric: true },
    { key: 'quantity_rejected', label: 'Qty rejected', type: 'number', step: 'any', min: 0, numeric: true },
    { key: 'rejection_reason', label: 'Rejection reason (optional)', required: false },
  ]), [grn]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (grn) {
      setRows(grn.items.map(i => blankRow(fields, {
        product_id: String(i.product_id), quantity_inspected: String(i.received_quantity),
        quantity_accepted: String(i.received_quantity), quantity_rejected: '0',
      })));
    } else setRows([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grnId]);

  const submit = (e) => {
    e.preventDefault();
    if (!grnId) return;
    const items = collectRows(rows, fields).map(i => ({
      product_id: Number(i.product_id), quantity_inspected: Number(i.quantity_inspected),
      quantity_accepted: Number(i.quantity_accepted), quantity_rejected: Number(i.quantity_rejected),
      rejection_reason: i.rejection_reason || undefined,
    }));
    if (!items.length) return;
    onSubmit({ grn_id: Number(grnId), inspected_by: inspectedBy || undefined, inspection_date: date, notes: notes || undefined, items });
  };

  return (
    <Modal open onClose={onClose} title="New quality inspection" wide>
      <form onSubmit={submit}>
        <div className="form-row-2">
          <div className="form-group"><label>Goods receipt</label>
            <select required value={grnId} onChange={(e) => setGrnId(e.target.value)}>
              <option value="" disabled hidden>Select…</option>
              {goodsReceipts.length === 0 && <option value="">No pending receipts to inspect</option>}
              {goodsReceipts.map(g => <option key={g.id} value={g.id}>{g.grn_number}</option>)}
            </select>
          </div>
          <div className="form-group"><label>Inspection date</label><input type="date" required max={todayISO()} value={date} onChange={(e) => setDate(e.target.value)} /></div>
        </div>
        <div className="form-row-2">
          <div className="form-group"><label>Inspected by (optional)</label><input type="text" value={inspectedBy} onChange={(e) => setInspectedBy(e.target.value)} /></div>
          <div className="form-group"><label>Notes (optional)</label><input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} /></div>
        </div>
        <div className="form-subhead">Line items</div>
        {grn ? (
          <LineItemsBuilder label="Inspection results" fields={fields} rows={rows} setRows={setRows} />
        ) : <div className="hint-text">Select a goods receipt to load its received line items.</div>}
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Log inspection</button>
        </div>
      </form>
    </Modal>
  );
}

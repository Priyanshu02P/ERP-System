import { useEffect, useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { useOverlay } from '../state/OverlayContext';
import { api } from '../api';
import { byId, fmtDate, fmtNum, todayISO } from '../utils/format';
import { productOptions, productLabel } from '../utils/options';
import { PBadge } from '../components/Badges';
import { DetailMeta } from '../components/DetailModal';
import Modal from '../components/Modal';
import LineItemsBuilder, { blankRow, collectRows } from '../components/LineItemsBuilder';

const LINE_FIELDS = [
  { key: 'product_id', label: 'Product', type: 'select', numeric: true },
  { key: 'quantity', label: 'Quantity', type: 'number', step: 'any', min: 0.001, numeric: true },
  { key: 'required_delivery_date', label: 'Required by (optional)', type: 'date', required: false },
];

export default function RFQs({ onNavigate, navParams }) {
  const { rfqs, suppliers, products, units, purchaseRequisitions, loadRFQs } = useAppData();
  const toast = useToast();
  const { openActionModal, openDetailModal, closeDetailModal } = useOverlay();

  const [search, setSearch] = useState('');
  const [fStatus, setFStatus] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [prefillPrId, setPrefillPrId] = useState(null);
  const [sendTarget, setSendTarget] = useState(null);

  useEffect(() => {
    if (navParams?.prId) { setPrefillPrId(navParams.prId); setCreateOpen(true); }
  }, [navParams]);

  const rows = rfqs.filter(r => {
    if (fStatus && r.status !== fStatus) return false;
    if (search && !`${r.rfq_number} ${r.delivery_location || ''}`.toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  }).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const closeRFQ = async (id) => {
    if (!window.confirm('Close this RFQ? Suppliers that never responded will be marked no-response.')) return;
    try { await api(`/rfqs/${id}/close`, { method: 'POST' }); closeDetailModal(); await loadRFQs(); toast('RFQ closed.'); }
    catch (err) { toast(err.message, 'error'); }
  };

  const openDetail = (r) => {
    const suppliersById = byId(suppliers);
    const itemsHtml = (
      <table className="detail-items-table">
        <thead><tr><th>Product</th><th>Quantity</th><th>Required by</th></tr></thead>
        <tbody>{r.items.map((i, idx) => <tr key={idx}><td>{productLabel(products, i.product_id)}</td><td className="mono">{fmtNum(i.quantity)}</td><td className="mono">{fmtDate(i.required_delivery_date)}</td></tr>)}</tbody>
      </table>
    );
    const suppliersHtml = r.suppliers.length ? (
      <table className="detail-items-table">
        <thead><tr><th>Supplier</th><th>Sent</th><th>Response</th></tr></thead>
        <tbody>{r.suppliers.map((s, idx) => <tr key={idx}><td>{suppliersById[s.supplier_id]?.name || '#' + s.supplier_id}</td><td className="mono">{fmtDate(s.sent_at)}</td><td><PBadge status={s.response_status} /></td></tr>)}</tbody>
      </table>
    ) : <div className="detail-note">Not sent to any suppliers yet.</div>;
    const actions = [];
    if (r.status === 'DRAFT') actions.push(<button key="send" className="btn btn-primary btn-sm" onClick={() => setSendTarget(r)}>Send to suppliers</button>);
    if (r.status === 'SENT' || r.status === 'RESPONSES_RECEIVED') {
      actions.push(<button key="quo" className="btn btn-secondary btn-sm" onClick={() => { closeDetailModal(); onNavigate('quotations', { rfqId: r.id }); }}>Log a quotation</button>);
      actions.push(<button key="close" className="btn btn-danger btn-sm" onClick={() => closeRFQ(r.id)}>Close RFQ</button>);
    }
    openDetailModal({
      title: `RFQ ${r.rfq_number}`,
      body: (
        <>
          <DetailMeta pairs={[['Due date', fmtDate(r.due_date)], ['Delivery location', r.delivery_location || '—'], ['Status', <PBadge status={r.status} key="s" />]]} />
          <div className="detail-section-label">Line items</div>{itemsHtml}
          <div className="detail-section-label">Suppliers</div>{suppliersHtml}
        </>
      ),
      actions: actions.length ? actions : null,
    });
  };

  return (
    <section className="page active">
      <div className="page-header">
        <div><h1>Requests for quotation</h1><p>Send line items out to suppliers and track who has responded.</p></div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => loadRFQs()}>⟳ Refresh</button>
          <button className="btn btn-primary" onClick={() => { setPrefillPrId(null); setCreateOpen(true); }}>+ New RFQ</button>
        </div>
      </div>
      <div className="toolbar">
        <div className="search-wrap"><span className="search-icon">⌕</span>
          <input type="text" placeholder="Search by RFQ number or delivery location…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="DRAFT">Draft</option><option value="SENT">Sent</option>
          <option value="RESPONSES_RECEIVED">Responses received</option>
          <option value="CLOSED">Closed</option><option value="CANCELLED">Cancelled</option>
        </select>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{rows.length} of {rfqs.length} RFQs</span>
      </div>
      <div className="table-container">
        <table>
          <thead><tr><th>RFQ number</th><th>Due date</th><th>Delivery location</th><th>Suppliers sent</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={6}><div className="empty-state"><div className="empty-icon">⇄</div><p>No RFQs match your filters.</p></div></td></tr>
            ) : rows.map(r => (
              <tr key={r.id}>
                <td className="mono">{r.rfq_number}</td>
                <td className="mono">{fmtDate(r.due_date)}</td>
                <td>{r.delivery_location || '—'}</td>
                <td className="mono">{r.suppliers.length}</td>
                <td><PBadge status={r.status} /></td>
                <td><div className="cell-actions"><button className="btn btn-ghost btn-sm" onClick={() => openDetail(r)}>View</button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {createOpen && (
        <RFQCreateModal
          products={products} units={units} purchaseRequisitions={purchaseRequisitions} prefillPrId={prefillPrId}
          onClose={() => setCreateOpen(false)}
          onSubmit={async (body) => {
            try {
              await api('/rfqs', { method: 'POST', body: JSON.stringify(body) });
              setCreateOpen(false); toast('RFQ created.'); await loadRFQs();
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}

      {sendTarget && (
        <RFQSendModal
          rfq={sendTarget} suppliers={suppliers.filter(s => s.is_active)}
          onClose={() => setSendTarget(null)}
          onSubmit={async (body) => {
            try {
              await api(`/rfqs/${sendTarget.id}/send`, { method: 'POST', body: JSON.stringify(body) });
              setSendTarget(null); closeDetailModal(); toast('RFQ sent.'); await loadRFQs();
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}
    </section>
  );
}

function RFQCreateModal({ products, units, purchaseRequisitions, prefillPrId, onClose, onSubmit }) {
  const fields = LINE_FIELDS.map(f => f.key === 'product_id' ? { ...f, options: productOptions(products, units) } : f);
  const [rows, setRows] = useState([blankRow(fields)]);
  const [dueDate, setDueDate] = useState('');
  const [deliveryLoc, setDeliveryLoc] = useState('');
  const [prId, setPrId] = useState(prefillPrId ? String(prefillPrId) : '');

  const approvedPRs = purchaseRequisitions.filter(p => p.status === 'APPROVED');

  const submit = (e) => {
    e.preventDefault();
    const items = collectRows(rows, fields).map(i => ({ product_id: Number(i.product_id), quantity: Number(i.quantity), required_delivery_date: i.required_delivery_date || undefined }));
    if (!items.length) return;
    onSubmit({ due_date: dueDate, delivery_location: deliveryLoc || undefined, pr_id: prId ? Number(prId) : undefined, items });
  };

  return (
    <Modal open onClose={onClose} title="New RFQ" wide>
      <form onSubmit={submit}>
        <div className="form-row-2">
          <div className="form-group"><label>Due date</label><input type="date" required min={todayISO()} value={dueDate} onChange={(e) => setDueDate(e.target.value)} /></div>
          <div className="form-group"><label>Linked requisition (optional)</label>
            <select value={prId} onChange={(e) => setPrId(e.target.value)}>
              <option value="">None</option>
              {approvedPRs.map(p => <option key={p.id} value={p.id}>{p.pr_number} — {p.department}</option>)}
            </select>
          </div>
        </div>
        <div className="form-group"><label>Delivery location (optional)</label><input type="text" placeholder="e.g. Main Warehouse, Dock 2" value={deliveryLoc} onChange={(e) => setDeliveryLoc(e.target.value)} /></div>
        <div className="form-subhead">Line items</div>
        <LineItemsBuilder label="Products to quote" fields={fields} rows={rows} setRows={setRows} />
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Create RFQ</button>
        </div>
      </form>
    </Modal>
  );
}

function RFQSendModal({ rfq, suppliers, onClose, onSubmit }) {
  const [selected, setSelected] = useState([]);
  const [channel, setChannel] = useState('API');
  const toast = useToast();

  const toggle = (id) => setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);

  const submit = (e) => {
    e.preventDefault();
    if (!selected.length) { toast('Select at least one supplier.', 'error'); return; }
    onSubmit({ supplier_ids: selected, channel });
  };

  return (
    <Modal open onClose={onClose} title="Send RFQ to suppliers">
      <div className="modal-context">
        <div className="ctx-name">{rfq.rfq_number}</div>
        <div className="ctx-sub">Choose which suppliers receive this RFQ.</div>
      </div>
      <form onSubmit={submit}>
        <div className="form-group">
          <label>Suppliers to send to</label>
          <div className="line-items-wrap" style={{ maxHeight: 220, overflowY: 'auto' }}>
            {suppliers.length === 0 ? <div className="empty-state"><p>No active suppliers.</p></div> : suppliers.map(s => (
              <label key={s.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0.2rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                <input type="checkbox" style={{ width: 'auto' }} checked={selected.includes(s.id)} onChange={() => toggle(s.id)} /> {s.code} — {s.name}
              </label>
            ))}
          </div>
        </div>
        <div className="form-group">
          <label>Channel</label>
          <select value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="API">API</option><option value="EMAIL">Email</option>
            <option value="WHATSAPP">WhatsApp</option><option value="TELEGRAM">Telegram</option>
          </select>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Send RFQ</button>
        </div>
      </form>
    </Modal>
  );
}

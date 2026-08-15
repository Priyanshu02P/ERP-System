import { useEffect, useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { useOverlay } from '../state/OverlayContext';
import { api } from '../api';
import { byId, fmtDate, fmtNum, money, itemsTotal, todayISO } from '../utils/format';
import { productOptions, productLabel } from '../utils/options';
import { PBadge } from '../components/Badges';
import { DetailMeta } from '../components/DetailModal';
import Modal from '../components/Modal';
import LineItemsBuilder, { blankRow, collectRows } from '../components/LineItemsBuilder';

const LINE_FIELDS = [
  { key: 'product_id', label: 'Product', type: 'select', numeric: true },
  { key: 'quantity', label: 'Qty', type: 'number', step: 'any', min: 0.001, numeric: true },
  { key: 'rate', label: 'Rate', type: 'number', step: 'any', min: 0, numeric: true },
  { key: 'gst_rate', label: 'GST % (optional)', type: 'number', step: 'any', min: 0, required: false, numeric: true },
];

export default function PurchaseOrders({ onNavigate, navParams }) {
  const { purchaseOrders, suppliers, quotations, products, units, loadPOs, loadQuotations } = useAppData();
  const toast = useToast();
  const { openActionModal, closeActionModal, openDetailModal, closeDetailModal } = useOverlay();

  const [search, setSearch] = useState('');
  const [fStatus, setFStatus] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [prefillQuotationId, setPrefillQuotationId] = useState(null);

  useEffect(() => {
    if (navParams?.quotationId) { setPrefillQuotationId(navParams.quotationId); setCreateOpen(true); }
  }, [navParams]);

  const rows = purchaseOrders.filter(p => {
    if (fStatus && p.status !== fStatus) return false;
    if (search && !p.po_number.toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  }).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const sendPO = (id) => {
    openActionModal({
      title: 'Send purchase order', fields: [{ key: 'approved_by', label: 'Approved by' }], submitLabel: 'Send',
      onSubmit: async (v) => { await api(`/purchase-orders/${id}/send`, { method: 'POST', body: JSON.stringify({ approved_by: v.approved_by }) }); closeDetailModal(); toast('Purchase order sent.'); await loadPOs(); },
    });
  };
  const confirmPO = async (id) => {
    if (!window.confirm('Mark this purchase order as confirmed by the supplier?')) return;
    try { await api(`/purchase-orders/${id}/confirm`, { method: 'POST' }); closeDetailModal(); await loadPOs(); toast('Purchase order confirmed.'); }
    catch (err) { toast(err.message, 'error'); }
  };
  const cancelPO = (id) => {
    openActionModal({
      title: 'Cancel purchase order', danger: true, submitLabel: 'Cancel PO',
      fields: [{ key: 'cancelled_by', label: 'Cancelled by' }, { key: 'cancellation_reason', label: 'Reason', type: 'textarea' }],
      onSubmit: async (v) => { await api(`/purchase-orders/${id}/cancel`, { method: 'POST', body: JSON.stringify({ cancelled_by: v.cancelled_by, cancellation_reason: v.cancellation_reason }) }); closeDetailModal(); toast('Purchase order cancelled.'); await loadPOs(); },
    });
  };

  const openDetail = (p) => {
    const itemsHtml = (
      <table className="detail-items-table">
        <thead><tr><th>Product</th><th>Qty</th><th>Received</th><th>Rate</th><th>Amount</th><th>Line status</th></tr></thead>
        <tbody>{p.items.map((i, idx) => <tr key={idx}><td>{productLabel(products, i.product_id)}</td><td className="mono">{fmtNum(i.quantity)}</td><td className="mono">{fmtNum(i.received_quantity)}</td><td className="mono">{money(i.rate)}</td><td className="mono">{money(i.amount)}</td><td><PBadge status={i.line_status} /></td></tr>)}</tbody>
      </table>
    );
    const actions = [];
    if (p.status === 'DRAFT') { actions.push(<button key="send" className="btn btn-primary btn-sm" onClick={() => sendPO(p.id)}>Send to supplier</button>); actions.push(<button key="cancel" className="btn btn-danger btn-sm" onClick={() => cancelPO(p.id)}>Cancel</button>); }
    if (p.status === 'SENT') { actions.push(<button key="confirm" className="btn btn-primary btn-sm" onClick={() => confirmPO(p.id)}>Confirm</button>); actions.push(<button key="cancel" className="btn btn-danger btn-sm" onClick={() => cancelPO(p.id)}>Cancel</button>); }
    if (['CONFIRMED', 'PARTIALLY_RECEIVED'].includes(p.status)) actions.push(<button key="grn" className="btn btn-secondary btn-sm" onClick={() => { closeDetailModal(); onNavigate('goods-receipts', { poId: p.id }); }}>Log goods receipt</button>);
    const note = p.status === 'CANCELLED' && p.cancellation_reason ? <div className="detail-note"><strong>Cancelled</strong> by {p.cancelled_by}: {p.cancellation_reason}</div> : null;
    openDetailModal({
      title: `PO ${p.po_number}`,
      body: (
        <>
          <DetailMeta pairs={[
            ['Supplier', suppliers.find(s => s.id === p.supplier_id)?.name || '—'], ['Order date', fmtDate(p.order_date)],
            ['Expected delivery', fmtDate(p.expected_delivery_date)], ['Payment terms', p.payment_terms || '—'],
            ['Subtotal', money(p.subtotal)], ['GST', money(p.gst_amount)], ['Total', money(p.total_amount)], ['Status', <PBadge status={p.status} key="s" />],
          ]} />
          {note}
          <div className="detail-section-label">Line items</div>{itemsHtml}
        </>
      ),
      actions: actions.length ? actions : null,
    });
  };

  return (
    <section className="page active">
      <div className="page-header">
        <div><h1>Purchase orders</h1><p>Committed orders placed with a supplier, from a selected quotation or manually.</p></div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => loadPOs()}>⟳ Refresh</button>
          <button className="btn btn-primary" onClick={() => { setPrefillQuotationId(null); setCreateOpen(true); }}>+ New purchase order</button>
        </div>
      </div>
      <div className="toolbar">
        <div className="search-wrap"><span className="search-icon">⌕</span>
          <input type="text" placeholder="Search by PO number…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="DRAFT">Draft</option><option value="SENT">Sent</option><option value="CONFIRMED">Confirmed</option>
          <option value="PARTIALLY_RECEIVED">Partially received</option><option value="RECEIVED">Received</option>
          <option value="CLOSED">Closed</option><option value="CANCELLED">Cancelled</option>
        </select>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{rows.length} of {purchaseOrders.length} purchase orders</span>
      </div>
      <div className="table-container">
        <table>
          <thead><tr><th>PO number</th><th>Supplier</th><th>Order date</th><th>Total</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={6}><div className="empty-state"><div className="empty-icon">⎘</div><p>No purchase orders match your filters.</p></div></td></tr>
            ) : rows.map(p => (
              <tr key={p.id}>
                <td className="mono">{p.po_number}</td>
                <td>{suppliers.find(s => s.id === p.supplier_id)?.name || '#' + p.supplier_id}</td>
                <td className="mono">{fmtDate(p.order_date)}</td>
                <td className="mono">{money(p.total_amount)}</td>
                <td><PBadge status={p.status} /></td>
                <td><div className="cell-actions"><button className="btn btn-ghost btn-sm" onClick={() => openDetail(p)}>View</button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {createOpen && (
        <POCreateModal
          products={products} units={units} suppliers={suppliers}
          quotations={quotations.filter(q => q.status === 'SELECTED')}
          prefillQuotationId={prefillQuotationId}
          onClose={() => setCreateOpen(false)}
          onSubmit={async (body) => {
            try {
              await api('/purchase-orders', { method: 'POST', body: JSON.stringify(body) });
              setCreateOpen(false); toast('Purchase order created.'); await Promise.all([loadPOs(), loadQuotations()]);
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}
    </section>
  );
}

function POCreateModal({ products, units, suppliers, quotations, prefillQuotationId, onClose, onSubmit }) {
  const fields = LINE_FIELDS.map(f => f.key === 'product_id' ? { ...f, options: productOptions(products, units) } : f);
  const [tab, setTab] = useState(prefillQuotationId ? 'quotation' : 'quotation');
  const [orderDate, setOrderDate] = useState(todayISO());
  const [expected, setExpected] = useState('');
  const [terms, setTerms] = useState('');
  const [quotationId, setQuotationId] = useState(prefillQuotationId ? String(prefillQuotationId) : '');
  const [supplierId, setSupplierId] = useState(suppliers[0]?.id ? String(suppliers[0].id) : '');
  const [rows, setRows] = useState([blankRow(fields)]);

  const submit = (e) => {
    e.preventDefault();
    const base = { order_date: orderDate, expected_delivery_date: expected || undefined, payment_terms: terms || undefined };
    if (tab === 'quotation') {
      if (!quotationId) return;
      onSubmit({ ...base, quotation_id: Number(quotationId) });
    } else {
      const items = collectRows(rows, fields).map(i => ({ product_id: Number(i.product_id), quantity: Number(i.quantity), rate: Number(i.rate), gst_rate: i.gst_rate !== undefined && i.gst_rate !== '' ? Number(i.gst_rate) : undefined }));
      if (!items.length || !supplierId) return;
      onSubmit({ ...base, supplier_id: Number(supplierId), items });
    }
  };

  return (
    <Modal open onClose={onClose} title="New purchase order" wide>
      <div className="tabs-row">
        <button type="button" className={`tab-btn${tab === 'quotation' ? ' active' : ''}`} onClick={() => setTab('quotation')}>From quotation</button>
        <button type="button" className={`tab-btn${tab === 'manual' ? ' active' : ''}`} onClick={() => setTab('manual')}>Manual</button>
      </div>
      <form onSubmit={submit}>
        <div className="form-row-2">
          <div className="form-group"><label>Order date</label><input type="date" required value={orderDate} onChange={(e) => setOrderDate(e.target.value)} /></div>
          <div className="form-group"><label>Expected delivery (optional)</label><input type="date" value={expected} onChange={(e) => setExpected(e.target.value)} /></div>
        </div>
        <div className="form-group"><label>Payment terms (optional)</label><input type="text" placeholder="e.g. Net 30" value={terms} onChange={(e) => setTerms(e.target.value)} /></div>

        {tab === 'quotation' && (
          <div className="tab-pane active">
            <div className="form-group"><label>Selected quotation</label>
              <select value={quotationId} onChange={(e) => setQuotationId(e.target.value)}>
                <option value="" disabled hidden>Select…</option>
                {quotations.length === 0 && <option value="">No selected quotations yet</option>}
                {quotations.map(q => <option key={q.id} value={q.id}>Quote #{q.id} — {suppliers.find(s => s.id === q.supplier_id)?.name || ''} — {money(itemsTotal(q.items))}</option>)}
              </select>
              <div className="hint-text">Supplier and line items are copied from the quotation automatically.</div>
            </div>
          </div>
        )}

        {tab === 'manual' && (
          <div className="tab-pane active">
            <div className="form-group"><label>Supplier</label>
              <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                {suppliers.map(s => <option key={s.id} value={s.id}>{s.code} — {s.name}</option>)}
              </select>
            </div>
            <LineItemsBuilder label="Line items" fields={fields} rows={rows} setRows={setRows} />
          </div>
        )}

        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Create purchase order</button>
        </div>
      </form>
    </Modal>
  );
}

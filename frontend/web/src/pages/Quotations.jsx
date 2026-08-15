import { useEffect, useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { useOverlay } from '../state/OverlayContext';
import { api } from '../api';
import { byId, fmtDate, fmtNum, money, itemsTotal } from '../utils/format';
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

export default function Quotations({ onNavigate, navParams }) {
  const { quotations, suppliers, rfqs, products, units, loadQuotations, loadRFQs } = useAppData();
  const toast = useToast();
  const { openActionModal, openDetailModal, closeDetailModal } = useOverlay();

  const [search, setSearch] = useState('');
  const [fStatus, setFStatus] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [prefillRfqId, setPrefillRfqId] = useState(null);

  useEffect(() => {
    if (navParams?.rfqId) { setPrefillRfqId(navParams.rfqId); setCreateOpen(true); }
  }, [navParams]);

  const rows = quotations.filter(q => {
    if (fStatus && q.status !== fStatus) return false;
    if (search && !`${q.vendor_quotation_no || ''}`.toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  }).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const reviewQuotation = (id) => {
    openActionModal({
      title: 'Mark quotation reviewed', fields: [{ key: 'reviewed_by', label: 'Reviewed by' }], submitLabel: 'Mark reviewed',
      onSubmit: async (v) => { await api(`/quotations/${id}/review`, { method: 'POST', body: JSON.stringify({ reviewed_by: v.reviewed_by }) }); closeDetailModal(); toast('Quotation reviewed.'); await loadQuotations(); },
    });
  };
  const selectQuotation = async (id) => {
    if (!window.confirm('Select this quotation as the winning quote?')) return;
    try { await api(`/quotations/${id}/select`, { method: 'POST' }); closeDetailModal(); await loadQuotations(); toast('Quotation selected.'); }
    catch (err) { toast(err.message, 'error'); }
  };
  const rejectQuotation = (id) => {
    openActionModal({
      title: 'Reject quotation', danger: true, submitLabel: 'Reject',
      fields: [{ key: 'rejected_by', label: 'Rejected by' }, { key: 'rejection_reason', label: 'Reason', type: 'textarea' }],
      onSubmit: async (v) => { await api(`/quotations/${id}/reject`, { method: 'POST', body: JSON.stringify({ rejected_by: v.rejected_by, rejection_reason: v.rejection_reason }) }); closeDetailModal(); toast('Quotation rejected.'); await loadQuotations(); },
    });
  };

  const openDetail = (q) => {
    const suppliersById = byId(suppliers);
    const itemsHtml = (
      <table className="detail-items-table">
        <thead><tr><th>Product</th><th>Qty</th><th>Rate</th><th>GST %</th><th>Amount</th></tr></thead>
        <tbody>{q.items.map((i, idx) => <tr key={idx}><td>{i.product_id ? productLabel(products, i.product_id) : i.raw_description}</td><td className="mono">{fmtNum(i.quantity)}</td><td className="mono">{money(i.rate)}</td><td className="mono">{i.gst_rate ?? '—'}</td><td className="mono">{money(i.amount)}</td></tr>)}</tbody>
      </table>
    );
    const actions = [];
    if (q.status === 'PENDING_REVIEW') actions.push(<button key="review" className="btn btn-primary btn-sm" onClick={() => reviewQuotation(q.id)}>Mark reviewed</button>);
    if (q.status === 'REVIEWED') actions.push(<button key="select" className="btn btn-primary btn-sm" onClick={() => selectQuotation(q.id)}>Select this quotation</button>);
    if (q.status === 'PENDING_REVIEW' || q.status === 'REVIEWED') actions.push(<button key="reject" className="btn btn-danger btn-sm" onClick={() => rejectQuotation(q.id)}>Reject</button>);
    if (q.status === 'SELECTED') actions.push(<button key="po" className="btn btn-secondary btn-sm" onClick={() => { closeDetailModal(); onNavigate('purchase-orders', { quotationId: q.id }); }}>Create PO from this</button>);
    const note = q.status === 'REJECTED' && q.rejection_reason ? <div className="detail-note"><strong>Rejected</strong> by {q.rejected_by}: {q.rejection_reason}</div> : null;
    openDetailModal({
      title: `Quotation #${q.id}`,
      body: (
        <>
          <DetailMeta pairs={[
            ['Supplier', suppliers.find(s => s.id === q.supplier_id)?.name || '—'], ['Vendor quote #', q.vendor_quotation_no || '—'],
            ['Quotation date', fmtDate(q.quotation_date)], ['Valid until', fmtDate(q.validity_date)],
            ['Payment terms', q.payment_terms || '—'], ['Lead time', q.delivery_lead_time_days != null ? q.delivery_lead_time_days + ' days' : '—'],
            ['Status', <PBadge status={q.status} key="s" />], ['Source', q.source],
          ]} />
          {note}
          <div className="detail-section-label">Line items — total {money(itemsTotal(q.items))}</div>{itemsHtml}
        </>
      ),
      actions: actions.length ? actions : null,
    });
  };

  return (
    <section className="page active">
      <div className="page-header">
        <div><h1>Vendor quotations</h1><p>Compare supplier pricing per RFQ, then select the winning quote.</p></div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => loadQuotations()}>⟳ Refresh</button>
          <button className="btn btn-primary" onClick={() => { setPrefillRfqId(null); setCreateOpen(true); }}>+ Log quotation</button>
        </div>
      </div>
      <div className="toolbar">
        <div className="search-wrap"><span className="search-icon">⌕</span>
          <input type="text" placeholder="Search by vendor quote number…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="PENDING_REVIEW">Pending review</option><option value="REVIEWED">Reviewed</option>
          <option value="SELECTED">Selected</option><option value="REJECTED">Rejected</option><option value="EXPIRED">Expired</option>
        </select>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{rows.length} of {quotations.length} quotations</span>
      </div>
      <div className="table-container">
        <table>
          <thead><tr><th>Supplier</th><th>RFQ</th><th>Vendor quote #</th><th>Total</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={6}><div className="empty-state"><div className="empty-icon">❖</div><p>No quotations match your filters.</p></div></td></tr>
            ) : rows.map(q => (
              <tr key={q.id}>
                <td>{suppliers.find(s => s.id === q.supplier_id)?.name || '#' + q.supplier_id}</td>
                <td className="mono">{q.rfq_id ? (rfqs.find(r => r.id === q.rfq_id)?.rfq_number || '#' + q.rfq_id) : '—'}</td>
                <td className="mono">{q.vendor_quotation_no || '—'}</td>
                <td className="mono">{money(itemsTotal(q.items))}</td>
                <td><PBadge status={q.status} /></td>
                <td><div className="cell-actions"><button className="btn btn-ghost btn-sm" onClick={() => openDetail(q)}>View</button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {createOpen && (
        <QuotationCreateModal
          products={products} units={units} suppliers={suppliers} rfqs={rfqs} prefillRfqId={prefillRfqId}
          onClose={() => setCreateOpen(false)}
          onSubmit={async (rfqId, body) => {
            try {
              await api(rfqId ? `/rfqs/${rfqId}/quotations` : '/quotations', { method: 'POST', body: JSON.stringify(body) });
              setCreateOpen(false); toast('Quotation logged.'); await Promise.all([loadQuotations(), loadRFQs()]);
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}
    </section>
  );
}

function QuotationCreateModal({ products, units, suppliers, rfqs, prefillRfqId, onClose, onSubmit }) {
  const fields = LINE_FIELDS.map(f => f.key === 'product_id' ? { ...f, options: productOptions(products, units) } : f);
  const [rows, setRows] = useState([blankRow(fields)]);
  const [rfqId, setRfqId] = useState(prefillRfqId ? String(prefillRfqId) : '');
  const [supplierId, setSupplierId] = useState(suppliers[0]?.id ? String(suppliers[0].id) : '');
  const [vendorNo, setVendorNo] = useState('');
  const [date, setDate] = useState('');
  const [validity, setValidity] = useState('');
  const [leadTime, setLeadTime] = useState('');
  const [terms, setTerms] = useState('');

  const submit = (e) => {
    e.preventDefault();
    const items = collectRows(rows, fields).map(i => ({ product_id: Number(i.product_id), quantity: Number(i.quantity), rate: Number(i.rate), gst_rate: i.gst_rate !== undefined && i.gst_rate !== '' ? Number(i.gst_rate) : undefined }));
    if (!items.length) return;
    onSubmit(rfqId || undefined, {
      supplier_id: Number(supplierId), vendor_quotation_no: vendorNo || undefined,
      quotation_date: date || undefined, validity_date: validity || undefined,
      payment_terms: terms || undefined, delivery_lead_time_days: leadTime ? Number(leadTime) : undefined, items,
    });
  };

  return (
    <Modal open onClose={onClose} title="Log vendor quotation" wide>
      <form onSubmit={submit}>
        <div className="form-row-2">
          <div className="form-group"><label>RFQ (optional)</label>
            <select value={rfqId} onChange={(e) => setRfqId(e.target.value)}>
              <option value="">None — standalone quotation</option>
              {rfqs.map(r => <option key={r.id} value={r.id}>{r.rfq_number}</option>)}
            </select>
          </div>
          <div className="form-group"><label>Supplier</label>
            <select required value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
              {suppliers.map(s => <option key={s.id} value={s.id}>{s.code} — {s.name}</option>)}
            </select>
          </div>
        </div>
        <div className="form-row-2">
          <div className="form-group"><label>Vendor quote # (optional)</label><input type="text" value={vendorNo} onChange={(e) => setVendorNo(e.target.value)} /></div>
          <div className="form-group"><label>Quotation date (optional)</label><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></div>
        </div>
        <div className="form-row-2">
          <div className="form-group"><label>Valid until (optional)</label><input type="date" value={validity} onChange={(e) => setValidity(e.target.value)} /></div>
          <div className="form-group"><label>Delivery lead time, days (optional)</label><input type="number" min="0" value={leadTime} onChange={(e) => setLeadTime(e.target.value)} /></div>
        </div>
        <div className="form-group"><label>Payment terms (optional)</label><input type="text" placeholder="e.g. Net 30" value={terms} onChange={(e) => setTerms(e.target.value)} /></div>
        <div className="form-subhead">Line items</div>
        <LineItemsBuilder label="Quoted products" fields={fields} rows={rows} setRows={setRows} />
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Log quotation</button>
        </div>
      </form>
    </Modal>
  );
}

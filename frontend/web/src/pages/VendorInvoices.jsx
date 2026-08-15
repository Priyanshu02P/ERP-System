import { useEffect, useMemo, useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { useOverlay } from '../state/OverlayContext';
import { api } from '../api';
import { byId, fmtDate, money, todayISO } from '../utils/format';
import { PBadge } from '../components/Badges';
import { DetailMeta } from '../components/DetailModal';
import Modal from '../components/Modal';

export default function VendorInvoices({ navParams }) {
  const { vendorInvoices, purchaseOrders, suppliers, loadInvoices, loadPOs } = useAppData();
  const toast = useToast();
  const { openActionModal, openDetailModal, closeDetailModal } = useOverlay();

  const [search, setSearch] = useState('');
  const [fStatus, setFStatus] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [prefillPoId, setPrefillPoId] = useState(null);

  useEffect(() => {
    if (navParams?.poId) { setPrefillPoId(navParams.poId); setCreateOpen(true); }
  }, [navParams]);

  const poById = useMemo(() => byId(purchaseOrders), [purchaseOrders]);
  const rows = vendorInvoices.filter(v => {
    if (fStatus && v.status !== fStatus) return false;
    if (search && !`${v.invoice_number}`.toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  }).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const approvePay = (id) => {
    openActionModal({
      title: 'Approve for payment', fields: [{ key: 'approved_by', label: 'Approved by' }], submitLabel: 'Approve',
      onSubmit: async (v) => { await api(`/vendor-invoices/${id}/approve`, { method: 'POST', body: JSON.stringify({ approved_by: v.approved_by }) }); closeDetailModal(); toast('Invoice approved for payment.'); await loadInvoices(); },
    });
  };
  const markPaid = (id) => {
    openActionModal({
      title: 'Mark as paid', fields: [{ key: 'payment_reference', label: 'Payment reference' }], submitLabel: 'Mark paid',
      onSubmit: async (v) => { await api(`/vendor-invoices/${id}/pay`, { method: 'POST', body: JSON.stringify({ payment_reference: v.payment_reference }) }); closeDetailModal(); toast('Invoice marked as paid.'); await loadInvoices(); },
    });
  };
  const disputeInvoice = (id) => {
    openActionModal({
      title: 'Dispute invoice', danger: true, submitLabel: 'Raise dispute',
      fields: [{ key: 'dispute_reason', label: 'Reason', type: 'textarea' }],
      onSubmit: async (v) => { await api(`/vendor-invoices/${id}/dispute`, { method: 'POST', body: JSON.stringify({ dispute_reason: v.dispute_reason }) }); closeDetailModal(); toast('Dispute raised.'); await loadInvoices(); },
    });
  };

  const openDetail = (v) => {
    const po = poById[v.po_id];
    const actions = [];
    if (['MATCHED', 'PENDING_MATCH'].includes(v.status)) actions.push(<button key="approve" className="btn btn-primary btn-sm" onClick={() => approvePay(v.id)}>Approve for payment</button>);
    if (v.status === 'APPROVED_FOR_PAYMENT') actions.push(<button key="pay" className="btn btn-primary btn-sm" onClick={() => markPaid(v.id)}>Mark paid</button>);
    if (!['PAID', 'DISPUTED'].includes(v.status)) actions.push(<button key="dispute" className="btn btn-danger btn-sm" onClick={() => disputeInvoice(v.id)}>Dispute</button>);
    const note = v.status === 'DISPUTED' && v.dispute_reason ? <div className="detail-note"><strong>Disputed:</strong> {v.dispute_reason}</div> : null;
    openDetailModal({
      title: `Invoice ${v.invoice_number}`,
      body: (
        <>
          <DetailMeta pairs={[
            ['Purchase order', po?.po_number || '#' + v.po_id], ['Supplier', suppliers.find(s => s.id === v.supplier_id)?.name || '—'],
            ['Invoice date', fmtDate(v.invoice_date)], ['Due date', fmtDate(v.due_date)],
            ['Amount', money(v.invoice_amount)], ['Match status', v.match_status || '—'], ['Status', <PBadge status={v.status} key="s" />],
          ]} />
          {note}
        </>
      ),
      actions: actions.length ? actions : null,
    });
  };

  return (
    <section className="page active">
      <div className="page-header">
        <div><h1>Vendor invoices</h1><p>Match supplier invoices against purchase orders and track payment status.</p></div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => loadInvoices()}>⟳ Refresh</button>
          <button className="btn btn-primary" onClick={() => { setPrefillPoId(null); setCreateOpen(true); }}>+ Log invoice</button>
        </div>
      </div>
      <div className="toolbar">
        <div className="search-wrap"><span className="search-icon">⌕</span>
          <input type="text" placeholder="Search by invoice number…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="PENDING_MATCH">Pending match</option><option value="MATCHED">Matched</option>
          <option value="MISMATCH">Mismatch</option><option value="APPROVED_FOR_PAYMENT">Approved for payment</option>
          <option value="PAID">Paid</option><option value="DISPUTED">Disputed</option>
        </select>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{rows.length} of {vendorInvoices.length} invoices</span>
      </div>
      <div className="table-container">
        <table>
          <thead><tr><th>Invoice #</th><th>PO</th><th>Supplier</th><th>Amount</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={6}><div className="empty-state"><div className="empty-icon">▤</div><p>No vendor invoices logged yet.</p></div></td></tr>
            ) : rows.map(v => (
              <tr key={v.id}>
                <td className="mono">{v.invoice_number}</td>
                <td className="mono">{poById[v.po_id]?.po_number || '#' + v.po_id}</td>
                <td>{suppliers.find(s => s.id === v.supplier_id)?.name || '#' + v.supplier_id}</td>
                <td className="mono">{money(v.invoice_amount)}</td>
                <td><PBadge status={v.status} /></td>
                <td><div className="cell-actions"><button className="btn btn-ghost btn-sm" onClick={() => openDetail(v)}>View</button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {createOpen && (
        <InvoiceCreateModal
          purchaseOrders={purchaseOrders} suppliers={suppliers} prefillPoId={prefillPoId}
          onClose={() => setCreateOpen(false)}
          onSubmit={async (body) => {
            try {
              await api('/vendor-invoices', { method: 'POST', body: JSON.stringify(body) });
              setCreateOpen(false); toast('Vendor invoice logged.'); await Promise.all([loadInvoices(), loadPOs()]);
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}
    </section>
  );
}

function InvoiceCreateModal({ purchaseOrders, suppliers, prefillPoId, onClose, onSubmit }) {
  const [poId, setPoId] = useState(prefillPoId ? String(prefillPoId) : '');
  const [invoiceNo, setInvoiceNo] = useState('');
  const [invoiceDate, setInvoiceDate] = useState(todayISO());
  const [dueDate, setDueDate] = useState('');
  const [amount, setAmount] = useState('');

  const po = purchaseOrders.find(p => String(p.id) === poId);

  const submit = (e) => {
    e.preventDefault();
    if (!poId) return;
    onSubmit({
      po_id: Number(poId), supplier_id: po?.supplier_id, invoice_number: invoiceNo,
      invoice_date: invoiceDate, due_date: dueDate || undefined, invoice_amount: Number(amount),
    });
  };

  return (
    <Modal open onClose={onClose} title="Log vendor invoice">
      <form onSubmit={submit}>
        <div className="form-group"><label>Purchase order</label>
          <select required value={poId} onChange={(e) => setPoId(e.target.value)}>
            <option value="" disabled hidden>Select…</option>
            {purchaseOrders.map(p => <option key={p.id} value={p.id}>{p.po_number} — {suppliers.find(s => s.id === p.supplier_id)?.name || ''} — {money(p.total_amount)}</option>)}
          </select>
        </div>
        <div className="form-row-2">
          <div className="form-group"><label>Invoice number</label><input type="text" required value={invoiceNo} onChange={(e) => setInvoiceNo(e.target.value)} /></div>
          <div className="form-group"><label>Invoice amount</label><input type="number" min="0" step="any" required value={amount} onChange={(e) => setAmount(e.target.value)} /></div>
        </div>
        <div className="form-row-2">
          <div className="form-group"><label>Invoice date</label><input type="date" required max={todayISO()} value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)} /></div>
          <div className="form-group"><label>Due date (optional)</label><input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} /></div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Log invoice</button>
        </div>
      </form>
    </Modal>
  );
}

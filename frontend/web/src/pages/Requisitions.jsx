import { useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { useOverlay } from '../state/OverlayContext';
import { api } from '../api';
import { fmtDate, fmtNum, todayISO } from '../utils/format';
import { productOptions, productLabel } from '../utils/options';
import { PBadge } from '../components/Badges';
import { DetailMeta } from '../components/DetailModal';
import Modal from '../components/Modal';
import LineItemsBuilder, { blankRow, collectRows } from '../components/LineItemsBuilder';

const LINE_FIELDS = [
  { key: 'product_id', label: 'Product', type: 'select', numeric: true },
  { key: 'quantity', label: 'Quantity', type: 'number', step: 'any', min: 0.001, numeric: true },
  { key: 'notes', label: 'Notes (optional)', required: false },
];

export default function Requisitions({ onNavigate }) {
  const data = useAppData();
  const { purchaseRequisitions, products, units, loadPRs } = data;
  const toast = useToast();
  const { openActionModal, closeActionModal, openDetailModal, closeDetailModal } = useOverlay();

  const [search, setSearch] = useState('');
  const [fStatus, setFStatus] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [prefill, setPrefill] = useState(null);

  const rows = purchaseRequisitions.filter(p => {
    if (fStatus && p.status !== fStatus) return false;
    if (search && !`${p.pr_number} ${p.department} ${p.raised_by}`.toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  }).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const submitPR = async (id) => {
    if (!window.confirm('Submit this requisition for approval?')) return;
    try { await api(`/purchase-requisitions/${id}/submit`, { method: 'POST' }); closeDetailModal(); toast('Requisition submitted.'); await loadPRs(); }
    catch (err) { toast(err.message, 'error'); }
  };
  const deletePR = async (id) => {
    if (!window.confirm('Delete this draft requisition? This cannot be undone.')) return;
    try { await api(`/purchase-requisitions/${id}`, { method: 'DELETE' }); closeDetailModal(); toast('Requisition deleted.'); await loadPRs(); }
    catch (err) { toast(err.message, 'error'); }
  };
  const approvePR = (id) => {
    openActionModal({
      title: 'Approve requisition', fields: [{ key: 'approved_by', label: 'Approved by' }], submitLabel: 'Approve',
      onSubmit: async (v) => { await api(`/purchase-requisitions/${id}/approve`, { method: 'POST', body: JSON.stringify({ approved_by: v.approved_by }) }); closeDetailModal(); toast('Requisition approved.'); await loadPRs(); },
    });
  };
  const rejectPR = (id) => {
    openActionModal({
      title: 'Reject requisition', danger: true, submitLabel: 'Reject',
      fields: [{ key: 'rejected_by', label: 'Rejected by' }, { key: 'rejection_reason', label: 'Reason', type: 'textarea' }],
      onSubmit: async (v) => { await api(`/purchase-requisitions/${id}/reject`, { method: 'POST', body: JSON.stringify({ rejected_by: v.rejected_by, rejection_reason: v.rejection_reason }) }); closeDetailModal(); toast('Requisition rejected.'); await loadPRs(); },
    });
  };

  const openDetail = (p) => {
    const itemsHtml = (
      <table className="detail-items-table">
        <thead><tr><th>Product</th><th>Quantity</th><th>Notes</th></tr></thead>
        <tbody>{p.items.map((i, idx) => <tr key={idx}><td>{productLabel(products, i.product_id)}</td><td className="mono">{fmtNum(i.quantity)}</td><td>{i.notes || '—'}</td></tr>)}</tbody>
      </table>
    );
    const actions = [];
    if (p.status === 'DRAFT') {
      actions.push(<button key="submit" className="btn btn-primary btn-sm" onClick={() => submitPR(p.id)}>Submit for approval</button>);
      actions.push(<button key="delete" className="btn btn-danger btn-sm" onClick={() => deletePR(p.id)}>Delete</button>);
    }
    if (p.status === 'PENDING_APPROVAL') {
      actions.push(<button key="approve" className="btn btn-primary btn-sm" onClick={() => approvePR(p.id)}>Approve</button>);
      actions.push(<button key="reject" className="btn btn-danger btn-sm" onClick={() => rejectPR(p.id)}>Reject</button>);
    }
    if (p.status === 'APPROVED') {
      actions.push(<button key="rfq" className="btn btn-secondary btn-sm" onClick={() => { closeDetailModal(); onNavigate('rfqs', { prId: p.id }); }}>Create RFQ from this</button>);
    }
    const note = p.status === 'REJECTED' && p.rejection_reason
      ? <div className="detail-note"><strong>Rejected</strong> by {p.rejected_by}: {p.rejection_reason}</div> : null;
    openDetailModal({
      title: `Requisition ${p.pr_number}`,
      body: (
        <>
          <DetailMeta pairs={[
            ['Department', p.department], ['Raised by', p.raised_by],
            ['Priority', p.priority === 'URGENT' ? 'Urgent' : 'Normal'], ['Required by', fmtDate(p.required_by_date)],
            ['Status', <PBadge status={p.status} key="s" />], ['Source', p.source],
          ]} />
          {p.reason && <div className="detail-note">{p.reason}</div>}
          {note}
          <div className="detail-section-label">Line items</div>
          {itemsHtml}
        </>
      ),
      actions: actions.length ? actions : null,
    });
  };

  return (
    <section className="page active">
      <div className="page-header">
        <div><h1>Purchase requisitions</h1><p>Internal requests to buy — the first step before an RFQ or purchase order exists.</p></div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => loadPRs()}>⟳ Refresh</button>
          <button className="btn btn-primary" onClick={() => { setPrefill(null); setCreateOpen(true); }}>+ New requisition</button>
        </div>
      </div>
      <div className="toolbar">
        <div className="search-wrap"><span className="search-icon">⌕</span>
          <input type="text" placeholder="Search by PR number, department, or requester…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="DRAFT">Draft</option><option value="PENDING_APPROVAL">Pending approval</option>
          <option value="APPROVED">Approved</option><option value="REJECTED">Rejected</option>
          <option value="CONVERTED">Converted</option><option value="CLOSED">Closed</option>
        </select>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{rows.length} of {purchaseRequisitions.length} requisitions</span>
      </div>
      <div className="table-container">
        <table>
          <thead><tr><th>PR number</th><th>Department</th><th>Raised by</th><th>Priority</th><th>Required by</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={7}><div className="empty-state"><div className="empty-icon">✎</div><p>No requisitions match your filters.</p></div></td></tr>
            ) : rows.map(p => (
              <tr key={p.id}>
                <td className="mono">{p.pr_number}</td>
                <td>{p.department}</td>
                <td>{p.raised_by}</td>
                <td>{p.priority === 'URGENT' ? <span className="pbadge pbadge-bad">Urgent</span> : <span className="pbadge pbadge-neutral">Normal</span>}</td>
                <td className="mono">{fmtDate(p.required_by_date)}</td>
                <td><PBadge status={p.status} /></td>
                <td><div className="cell-actions"><button className="btn btn-ghost btn-sm" onClick={() => openDetail(p)}>View</button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {createOpen && (
        <PRCreateModal
          products={products} units={units} prefill={prefill}
          onClose={() => setCreateOpen(false)}
          onSubmit={async (body) => {
            try {
              await api('/purchase-requisitions', { method: 'POST', body: JSON.stringify(body) });
              setCreateOpen(false); toast('Requisition created.'); await loadPRs();
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}
    </section>
  );
}

function PRCreateModal({ products, units, prefill, onClose, onSubmit }) {
  const fields = LINE_FIELDS.map(f => f.key === 'product_id' ? { ...f, options: productOptions(products, units) } : f);
  const [rows, setRows] = useState([blankRow(fields, prefill || {})]);
  const [department, setDepartment] = useState('');
  const [raisedBy, setRaisedBy] = useState('');
  const [priority, setPriority] = useState('NORMAL');
  const [requiredBy, setRequiredBy] = useState('');
  const [reason, setReason] = useState('');
  const [salesOrder, setSalesOrder] = useState('');

  const submit = (e) => {
    e.preventDefault();
    const items = collectRows(rows, fields).map(i => ({ product_id: Number(i.product_id), quantity: Number(i.quantity), notes: i.notes || undefined }));
    if (!items.length) return;
    onSubmit({
      department, raised_by: raisedBy, priority, required_by_date: requiredBy,
      reason: reason || undefined, linked_sales_order: salesOrder || undefined, items,
    });
  };

  return (
    <Modal open onClose={onClose} title="New purchase requisition" wide>
      <form onSubmit={submit}>
        <div className="form-row-2">
          <div className="form-group"><label>Department</label><input type="text" placeholder="e.g. Production" required value={department} onChange={(e) => setDepartment(e.target.value)} /></div>
          <div className="form-group"><label>Raised by</label><input type="text" placeholder="Your name" required value={raisedBy} onChange={(e) => setRaisedBy(e.target.value)} /></div>
        </div>
        <div className="form-row-2">
          <div className="form-group"><label>Priority</label>
            <select value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="NORMAL">Normal</option><option value="URGENT">Urgent</option>
            </select>
          </div>
          <div className="form-group"><label>Required by</label><input type="date" required min={todayISO()} value={requiredBy} onChange={(e) => setRequiredBy(e.target.value)} /></div>
        </div>
        <div className="form-group"><label>Reason (optional)</label><textarea rows={2} placeholder="Why this is needed" value={reason} onChange={(e) => setReason(e.target.value)} /></div>
        <div className="form-group"><label>Linked sales order (optional)</label><input type="text" placeholder="e.g. SO-2201" value={salesOrder} onChange={(e) => setSalesOrder(e.target.value)} /></div>
        <div className="form-subhead">Line items</div>
        <LineItemsBuilder label="Products needed" fields={fields} rows={rows} setRows={setRows} />
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Create requisition</button>
        </div>
      </form>
    </Modal>
  );
}

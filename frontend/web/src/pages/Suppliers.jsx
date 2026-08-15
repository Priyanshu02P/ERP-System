import { useMemo, useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { api } from '../api';
import { labelize } from '../utils/format';
import { PBadge } from '../components/Badges';
import Modal from '../components/Modal';

const CATEGORIES = ['STEEL', 'STAINLESS_STEEL', 'ALUMINIUM', 'HARDWARE', 'POWDER_COATING', 'PACKAGING', 'LOGISTICS', 'CONSUMABLES', 'OTHER'];

export default function Suppliers() {
  const { suppliers, manufacturers, loadSuppliers } = useAppData();
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [fCat, setFCat] = useState('');
  const [createOpen, setCreateOpen] = useState(false);

  const categories = useMemo(() => [...new Set(suppliers.map(s => s.category))].sort(), [suppliers]);

  const rows = suppliers.filter(s => {
    if (fCat && s.category !== fCat) return false;
    if (search && !`${s.code} ${s.name} ${s.gstin || ''}`.toLowerCase().includes(search.trim().toLowerCase())) return false;
    return true;
  });

  const toggleActive = async (id, makeActive) => {
    try {
      await api(`/suppliers/${id}/${makeActive ? 'activate' : 'deactivate'}`, { method: 'POST' });
      toast(makeActive ? 'Supplier activated.' : 'Supplier deactivated.');
      await loadSuppliers();
    } catch (err) { toast(err.message, 'error'); }
  };

  return (
    <section className="page active">
      <div className="page-header">
        <div>
          <h1>Suppliers</h1>
          <p>Vendor master data used across RFQs, quotations, purchase orders, and invoices.</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => loadSuppliers()}>⟳ Refresh</button>
          <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>+ New supplier</button>
        </div>
      </div>
      <div className="toolbar">
        <div className="search-wrap"><span className="search-icon">⌕</span>
          <input type="text" placeholder="Search by code, name, or GSTIN…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <select value={fCat} onChange={(e) => setFCat(e.target.value)}>
          <option value="">All categories</option>
          {categories.map(c => <option key={c} value={c}>{labelize(c)}</option>)}
        </select>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{rows.length} of {suppliers.length} suppliers</span>
      </div>
      <div className="table-container">
        <table>
          <thead><tr><th>Code</th><th>Name</th><th>Category</th><th>Contact</th><th>Payment terms</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={7}><div className="empty-state"><div className="empty-icon">⚑</div><p>No suppliers match your filters.</p></div></td></tr>
            ) : rows.map(s => (
              <tr key={s.id}>
                <td className="mono">{s.code}</td>
                <td>{s.name}</td>
                <td>{labelize(s.category)}</td>
                <td>{s.contact_person || '—'}{s.phone ? <div className="product-sub">{s.phone}</div> : null}</td>
                <td>{s.default_payment_terms || '—'}</td>
                <td>{s.is_active ? <span className="pbadge pbadge-good">Active</span> : <span className="pbadge pbadge-neutral">Inactive</span>}</td>
                <td><div className="cell-actions">
                  <button className="btn btn-secondary btn-sm" onClick={() => toggleActive(s.id, !s.is_active)}>{s.is_active ? 'Deactivate' : 'Activate'}</button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {createOpen && (
        <SupplierCreateModal
          manufacturers={manufacturers}
          onClose={() => setCreateOpen(false)}
          onSubmit={async (body) => {
            try {
              await api('/suppliers', { method: 'POST', body: JSON.stringify(body) });
              setCreateOpen(false); toast('Supplier created.'); await loadSuppliers();
            } catch (err) { toast(err.message, 'error'); }
          }}
        />
      )}
    </section>
  );
}

function SupplierCreateModal({ manufacturers, onClose, onSubmit }) {
  const [form, setForm] = useState({
    code: '', category: CATEGORIES[0], name: '', gstin: '', manufacturer_id: '',
    address: '', contact_person: '', phone: '', email: '', default_payment_terms: '',
  });
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  const submit = (e) => {
    e.preventDefault();
    onSubmit({
      code: form.code, name: form.name, gstin: form.gstin || null, address: form.address || null,
      contact_person: form.contact_person || null, phone: form.phone || null, email: form.email || null,
      category: form.category, default_payment_terms: form.default_payment_terms || null,
      manufacturer_id: form.manufacturer_id ? Number(form.manufacturer_id) : null,
    });
  };

  return (
    <Modal open onClose={onClose} title="New supplier">
      <form onSubmit={submit}>
        <div className="form-row-2">
          <div className="form-group"><label>Code</label><input type="text" placeholder="e.g. SUP-014" required value={form.code} onChange={set('code')} /></div>
          <div className="form-group"><label>Category</label>
            <select required value={form.category} onChange={set('category')}>
              {CATEGORIES.map(c => <option key={c} value={c}>{labelize(c)}</option>)}
            </select>
          </div>
        </div>
        <div className="form-group"><label>Name</label><input type="text" required value={form.name} onChange={set('name')} /></div>
        <div className="form-row-2">
          <div className="form-group"><label>GSTIN (optional)</label><input type="text" maxLength={15} value={form.gstin} onChange={set('gstin')} /></div>
          <div className="form-group"><label>Linked manufacturer (optional)</label>
            <select value={form.manufacturer_id} onChange={set('manufacturer_id')}>
              <option value="">None</option>
              {manufacturers.map(m => <option key={m.id} value={m.id}>{m.code} — {m.name}</option>)}
            </select>
          </div>
        </div>
        <div className="form-group"><label>Address (optional)</label><input type="text" value={form.address} onChange={set('address')} /></div>
        <div className="form-row-2">
          <div className="form-group"><label>Contact person (optional)</label><input type="text" value={form.contact_person} onChange={set('contact_person')} /></div>
          <div className="form-group"><label>Phone (optional)</label><input type="text" value={form.phone} onChange={set('phone')} /></div>
        </div>
        <div className="form-row-2">
          <div className="form-group"><label>Email (optional)</label><input type="email" value={form.email} onChange={set('email')} /></div>
          <div className="form-group"><label>Default payment terms (optional)</label><input type="text" placeholder="e.g. Net 30" value={form.default_payment_terms} onChange={set('default_payment_terms')} /></div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Create supplier</button>
        </div>
      </form>
    </Modal>
  );
}

import { useAppData } from '../state/AppDataContext';
import { fmtNum, money } from '../utils/format';
import { productLabel } from '../utils/options';

export default function ProcurementOverview({ onNavigate }) {
  const { procKPIs, reorderSuggestions, products, loadProcurementOverview } = useAppData();

  return (
    <section className="page active">
      <div className="page-header">
        <div><h1>Procurement overview</h1><p>Key metrics across the buy-side workflow, plus products that need reordering.</p></div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => loadProcurementOverview()}>⟳ Refresh</button>
        </div>
      </div>

      <div className="stats-row">
        <div className="stat-card"><span className="stat-label">Open requisitions</span><span className="stat-val">{procKPIs?.open_requisitions ?? '—'}</span></div>
        <div className="stat-card"><span className="stat-label">Open RFQs</span><span className="stat-val">{procKPIs?.open_rfqs ?? '—'}</span></div>
        <div className="stat-card"><span className="stat-label">Open purchase orders</span><span className="stat-val">{procKPIs?.open_purchase_orders ?? '—'}</span></div>
        <div className="stat-card"><span className="stat-label">Pending inspections</span><span className="stat-val">{procKPIs?.pending_inspections ?? '—'}</span></div>
        <div className="stat-card"><span className="stat-label">Unpaid invoices</span><span className="stat-val">{procKPIs ? money(procKPIs.unpaid_invoice_amount ?? 0) : '—'}</span></div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.05rem' }}>Reorder suggestions</h2>
          <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('requisitions')}>Go to requisitions →</button>
        </div>
        {reorderSuggestions.length === 0 ? (
          <div className="empty-state"><div className="empty-icon">⌘</div><p>No products currently need reordering.</p></div>
        ) : (
          <div className="table-container" style={{ boxShadow: 'none', border: 'none' }}>
            <table>
              <thead><tr><th>Product</th><th>Available</th><th>Reorder point</th><th>Suggested qty</th></tr></thead>
              <tbody>
                {reorderSuggestions.map((s, i) => (
                  <tr key={i}>
                    <td>{s.product_id ? productLabel(products, s.product_id) : (s.product_name || '—')}</td>
                    <td className="mono">{fmtNum(s.available_quantity)}</td>
                    <td className="mono">{fmtNum(s.reorder_point)}</td>
                    <td className="mono">{fmtNum(s.suggested_quantity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

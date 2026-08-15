import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { fmtNum } from '../utils/format';

export default function Dashboard({ onNavigate, onOpenReceive }) {
  const { products, inventory, logs, triggerSeed } = useAppData();
  const toast = useToast();

  const totalRecords = inventory.length;
  const totalUnits = inventory.reduce((sum, i) => sum + Number(i.quantity), 0);
  const flagged = inventory.filter(i => i.status !== 'OK').length;
  const recent = logs.slice(0, 6);

  const doSeed = async (clean) => {
    try {
      const result = await triggerSeed(clean);
      if (result.status === 'skipped') {
        toast('Database already seeded — use "Reset & reseed" to start over.');
      } else {
        toast('Sample data seeded.');
      }
    } catch (err) { toast(err.message, 'error'); }
  };

  return (
    <section className="page active">
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Live snapshot of stock on hand across every warehouse zone.</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => doSeed(false)}>⟳ Seed sample data</button>
          <button className="btn btn-primary" onClick={() => { onNavigate('inventory'); onOpenReceive(); }}>+ Receive stock</button>
        </div>
      </div>

      <div className="stats-row">
        <div className="stat-card"><span className="stat-label">SKUs tracked</span><span className="stat-val">{products.length}</span></div>
        <div className="stat-card"><span className="stat-label">Stock records</span><span className="stat-val">{totalRecords}</span></div>
        <div className="stat-card"><span className="stat-label">Units on hand</span><span className="stat-val">{fmtNum(totalUnits)}</span></div>
        <div className="stat-card"><span className="stat-label">On hold / flagged</span><span className="stat-val">{flagged}</span></div>
      </div>

      <div className="dash-grid">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.05rem' }}>Recent activity</h2>
            <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('logs')}>View all →</button>
          </div>
          <div>
            {recent.length === 0 ? (
              <div className="empty-state"><p>No activity yet. Seed sample data or receive stock to get started.</p></div>
            ) : (
              recent.map((l, i) => (
                <div className="activity-item" key={i}>
                  <span className={`action-badge act-${l.action}`}>{l.action}</span>
                  <span className="activity-detail">{l.entity}{l.entity_id ? ' #' + l.entity_id : ''}</span>
                  <span className="activity-time">{new Date(l.timestamp).toLocaleTimeString()}</span>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="card">
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.05rem' }}>Quick actions</h2>
          <div className="quick-actions">
            <button className="btn btn-secondary" style={{ justifyContent: 'flex-start' }} onClick={() => { onNavigate('inventory'); onOpenReceive(); }}>+ Receive new stock</button>
            <button className="btn btn-secondary" style={{ justifyContent: 'flex-start' }} onClick={() => onNavigate('inventory')}>▦ Browse inventory</button>
            <button className="btn btn-secondary" style={{ justifyContent: 'flex-start' }} onClick={() => onNavigate('logs')}>☰ Review transaction log</button>
            <button className="btn btn-secondary" style={{ justifyContent: 'flex-start' }} onClick={() => doSeed(true)}>⟳ Reset &amp; reseed demo data</button>
          </div>
        </div>
      </div>
    </section>
  );
}

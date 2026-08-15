import { useEffect, useRef, useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { useToast } from '../state/ToastContext';
import { fmtDate } from '../utils/format';

const ACTIONS = ['RECEIVE', 'ISSUE', 'MOVE', 'RESERVE', 'RELEASE', 'STATUS_CHANGE', 'ADJUST', 'DELETE', 'SEED'];

export default function Logs() {
  const { logs, loadLogs } = useAppData();
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [action, setAction] = useState('');
  const debounceRef = useRef(null);

  const refresh = async (a, s) => {
    try { await loadLogs({ action: a, search: s }); } catch (err) { toast(err.message, 'error'); }
  };

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => refresh(action, search), 150);
    return () => clearTimeout(debounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, action]);

  return (
    <section className="page active">
      <div className="page-header">
        <div>
          <h1>Activity logs</h1>
          <p>Structured audit trail of every stock movement — read from <code className="mono">backend/transaction.log</code>.</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => refresh(action, search)}>⟳ Refresh</button>
        </div>
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <span className="search-icon">⌕</span>
          <input type="text" placeholder="Search log details…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="">All actions</option>
          {ACTIONS.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{logs.length} entries</span>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr><th>Timestamp</th><th>Action</th><th>Entity</th><th>ID</th><th>Details</th></tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr><td colSpan={5}>
                <div className="empty-state">
                  <div className="empty-icon">☰</div><p>No log entries yet.</p>
                  <div className="empty-sub">Actions like receiving or dispatching stock will appear here.</div>
                </div>
              </td></tr>
            ) : logs.map((l, i) => (
              <tr key={i}>
                <td className="mono">{fmtDate(l.timestamp)} <span style={{ color: 'var(--text-faint)' }}>{new Date(l.timestamp).toLocaleTimeString()}</span></td>
                <td><span className={`action-badge act-${l.action}`}>{l.action}</span></td>
                <td>{l.entity}</td>
                <td className="mono">{l.entity_id ?? '—'}</td>
                <td className="mono" style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>{JSON.stringify(l.details)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

import { STATUS_LABEL, PROC_SEMANTIC, labelize } from '../utils/format';

export function StatusBadge({ status }) {
  const cls = `badge-${status.toLowerCase()}`;
  const pulse = status === 'OK' ? ' pulse' : '';
  return (
    <span className={`badge ${cls}`}>
      <span className={`led${pulse}`}></span>
      {STATUS_LABEL[status] || status}
    </span>
  );
}

export function TypeBadge({ type }) {
  const label = { RAW: 'Raw', WIP: 'WIP', FG: 'Finished' }[type] || type;
  return <span className={`type-badge type-${type}`}>{label}</span>;
}

export function PBadge({ status }) {
  const sem = PROC_SEMANTIC[status] || 'neutral';
  return <span className={`pbadge pbadge-${sem}`}>{labelize(status)}</span>;
}

export function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function fmtNum(n) {
  if (n === null || n === undefined) return '—';
  const num = Number(n);
  return Number.isInteger(num) ? num.toString() : num.toFixed(2).replace(/\.?0+$/, '');
}

export function money(n) {
  if (n === null || n === undefined) return '—';
  return '₹' + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function labelize(s) {
  if (!s) return '—';
  return String(s).split('_').map(w => w.charAt(0) + w.slice(1).toLowerCase()).join(' ');
}

export function byId(arr) {
  return Object.fromEntries((arr || []).map(x => [x.id, x]));
}

export function todayISO() {
  return new Date().toISOString().split('T')[0];
}

export const STATUS_LABEL = { OK: 'OK', HLD: 'On hold', DMG: 'Damaged', RJC: 'Rejected', MIS: 'Missing', RET: 'Returned' };

export const PROC_SEMANTIC = {
  DRAFT: 'neutral', PENDING_APPROVAL: 'progress', APPROVED: 'good', REJECTED: 'bad', CONVERTED: 'info', CLOSED: 'neutral',
  SENT: 'progress', RESPONSES_RECEIVED: 'info', CANCELLED: 'bad',
  PENDING_REVIEW: 'progress', REVIEWED: 'info', SELECTED: 'good', EXPIRED: 'neutral',
  CONFIRMED: 'info', PARTIALLY_RECEIVED: 'progress', RECEIVED: 'good',
  PENDING_QC: 'progress', QC_IN_PROGRESS: 'info',
  ACCEPTED: 'good', ACCEPTED_WITH_DEVIATION: 'progress', PARTIAL: 'info',
  PENDING_MATCH: 'progress', MATCHED: 'info', MISMATCH: 'bad', APPROVED_FOR_PAYMENT: 'good', PAID: 'good', DISPUTED: 'bad',
};

export function itemsTotal(items) {
  return (items || []).reduce((sum, i) => sum + Number(i.amount || 0), 0);
}

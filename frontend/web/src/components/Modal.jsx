export default function Modal({ open, onClose, wide, title, children, footer }) {
  if (!open) return null;
  return (
    <div
      className="modal-overlay open"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className={`modal${wide ? ' modal-wide' : ''}`}>
        <div className="modal-head">
          <span className="modal-title">{title}</span>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

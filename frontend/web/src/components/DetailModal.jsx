import Modal from './Modal';
import { useOverlay } from '../state/OverlayContext';

export function DetailMeta({ pairs }) {
  return (
    <div className="detail-meta">
      {pairs.map(([label, val], i) => (
        <div key={i}>
          <div className="dm-label">{label}</div>
          <div className="dm-val">{val}</div>
        </div>
      ))}
    </div>
  );
}

export default function DetailModal() {
  const { detailModal, closeDetailModal } = useOverlay();
  if (!detailModal) return null;
  const { title, body, actions } = detailModal;

  return (
    <Modal open={!!detailModal} onClose={closeDetailModal} title={title} wide>
      <div>
        {body}
        {actions && <div className="detail-actions-row">{actions}</div>}
      </div>
    </Modal>
  );
}

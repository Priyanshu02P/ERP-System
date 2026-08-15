import { useEffect, useState } from 'react';
import Modal from './Modal';
import { useOverlay } from '../state/OverlayContext';
import { useToast } from '../state/ToastContext';

export default function ActionModal() {
  const { actionModal, closeActionModal } = useOverlay();
  const toast = useToast();
  const [values, setValues] = useState({});

  useEffect(() => {
    if (actionModal) {
      const initial = {};
      actionModal.fields.forEach(f => { initial[f.key] = ''; });
      setValues(initial);
    }
  }, [actionModal]);

  if (!actionModal) return null;
  const { title, context, fields, submitLabel, danger, onSubmit } = actionModal;

  const submit = async (e) => {
    e.preventDefault();
    try {
      await onSubmit(values);
      closeActionModal();
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  return (
    <Modal open={!!actionModal} onClose={closeActionModal} title={title}>
      {context && <div className="modal-context">{context}</div>}
      <form onSubmit={submit}>
        <div>
          {fields.map(f => (
            <div className="form-group" key={f.key}>
              <label>{f.label}</label>
              {f.type === 'textarea' ? (
                <textarea
                  rows={2}
                  placeholder={f.placeholder || ''}
                  required={f.required !== false}
                  value={values[f.key] || ''}
                  onChange={(e) => setValues(v => ({ ...v, [f.key]: e.target.value }))}
                />
              ) : (
                <input
                  type="text"
                  placeholder={f.placeholder || ''}
                  required={f.required !== false}
                  value={values[f.key] || ''}
                  onChange={(e) => setValues(v => ({ ...v, [f.key]: e.target.value }))}
                />
              )}
            </div>
          ))}
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={closeActionModal}>Cancel</button>
          <button type="submit" className={danger ? 'btn btn-danger' : 'btn btn-primary'}>{submitLabel || 'Confirm'}</button>
        </div>
      </form>
    </Modal>
  );
}

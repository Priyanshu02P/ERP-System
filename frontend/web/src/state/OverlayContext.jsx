import { createContext, useCallback, useContext, useState } from 'react';

const OverlayCtx = createContext(null);

export function OverlayProvider({ children }) {
  const [actionModal, setActionModal] = useState(null); // { title, context, fields, submitLabel, danger, onSubmit }
  const [detailModal, setDetailModal] = useState(null); // { title, body, actions }

  const openActionModal = useCallback((config) => setActionModal(config), []);
  const closeActionModal = useCallback(() => setActionModal(null), []);

  const openDetailModal = useCallback((config) => setDetailModal(config), []);
  const closeDetailModal = useCallback(() => setDetailModal(null), []);

  return (
    <OverlayCtx.Provider value={{ actionModal, openActionModal, closeActionModal, detailModal, openDetailModal, closeDetailModal }}>
      {children}
    </OverlayCtx.Provider>
  );
}

export function useOverlay() {
  return useContext(OverlayCtx);
}

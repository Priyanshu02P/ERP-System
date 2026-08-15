import { createContext, useCallback, useContext, useRef, useState } from 'react';

const ToastCtx = createContext(null);

export function ToastProvider({ children }) {
  const [toastState, setToastState] = useState({ show: false, msg: '', type: 'success' });
  const timerRef = useRef(null);

  const toast = useCallback((msg, type = 'success') => {
    setToastState({ show: true, msg, type });
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setToastState(s => ({ ...s, show: false })), 3200);
  }, []);

  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div className={`toast ${toastState.show ? `show ${toastState.type}` : ''}`}>
        <span>{toastState.msg}</span>
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  return useContext(ToastCtx);
}

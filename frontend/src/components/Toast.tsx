import { useEffect, useRef } from "react";

import { useToastStore } from "../stores/useToastStore";

export function Toast() {
  const toasts = useToastStore((state) => state.toasts);
  const removeToast = useToastStore((state) => state.removeToast);
  const timerMapRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    const activeIds = new Set(toasts.map((toast) => toast.id));

    for (const toast of toasts) {
      if (timerMapRef.current.has(toast.id)) {
        continue;
      }

      const timerId = window.setTimeout(() => {
        removeToast(toast.id);
        timerMapRef.current.delete(toast.id);
      }, toast.duration);

      timerMapRef.current.set(toast.id, timerId);
    }

    for (const [id, timerId] of timerMapRef.current.entries()) {
      if (activeIds.has(id)) {
        continue;
      }

      window.clearTimeout(timerId);
      timerMapRef.current.delete(id);
    }
  }, [toasts, removeToast]);

  useEffect(() => {
    return () => {
      for (const timerId of timerMapRef.current.values()) {
        window.clearTimeout(timerId);
      }
      timerMapRef.current.clear();
    };
  }, []);

  return (
    <div className="toast-container" aria-live="polite" aria-atomic="true">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          {toast.message}
        </div>
      ))}
    </div>
  );
}

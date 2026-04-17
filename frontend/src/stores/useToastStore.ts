import { create } from "zustand";

export type ToastType = "success" | "error" | "warning";

export interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  duration: number;
}

interface ToastState {
  toasts: ToastItem[];
  addToast: (type: ToastType, message: string, duration?: number) => void;
  removeToast: (id: string) => void;
}

const MAX_TOASTS = 5;

function createToastId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getDefaultDuration(type: ToastType): number {
  return type === "error" ? 5000 : 3000;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (type, message, duration) => {
    const nextToast: ToastItem = {
      id: createToastId(),
      type,
      message,
      duration: duration ?? getDefaultDuration(type),
    };

    set((state) => {
      const nextQueue = [...state.toasts, nextToast];
      if (nextQueue.length <= MAX_TOASTS) {
        return { toasts: nextQueue };
      }

      return { toasts: nextQueue.slice(nextQueue.length - MAX_TOASTS) };
    });
  },
  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((toast) => toast.id !== id),
    }));
  },
}));

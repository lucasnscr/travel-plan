import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { create } from "zustand";
import { X, CheckCircle, AlertTriangle, Info, XCircle } from "lucide-react";
import { cn } from "@/utils/cn";

// --- Store ---

type ToastVariant = "success" | "error" | "warning" | "info";

interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
  duration: number;
}

interface ToastState {
  toasts: ToastItem[];
  add: (message: string, variant?: ToastVariant, duration?: number) => void;
  dismiss: (id: string) => void;
}

let nextId = 0;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  add: (message, variant = "info", duration = 4000) => {
    const id = String(++nextId);
    set((s) => ({ toasts: [...s.toasts, { id, message, variant, duration }] }));
  },
  dismiss: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

/** Helper to fire toasts from anywhere */
export const toast = {
  success: (msg: string) => useToastStore.getState().add(msg, "success"),
  error: (msg: string) => useToastStore.getState().add(msg, "error", 6000),
  warning: (msg: string) => useToastStore.getState().add(msg, "warning"),
  info: (msg: string) => useToastStore.getState().add(msg, "info"),
};

// --- Icons ---

const icons: Record<ToastVariant, typeof Info> = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const variantStyles: Record<ToastVariant, string> = {
  success: "border-emerald-500/30 text-emerald-300",
  error: "border-red-500/30 text-red-300",
  warning: "border-amber-500/30 text-amber-300",
  info: "border-brand-500/30 text-brand-300",
};

// --- Component ---

function ToastItem({ item }: { item: ToastItem }) {
  const { dismiss } = useToastStore();

  useEffect(() => {
    const timer = setTimeout(() => dismiss(item.id), item.duration);
    return () => clearTimeout(timer);
  }, [item.id, item.duration, dismiss]);

  const Icon = icons[item.variant];

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "pointer-events-auto flex items-start gap-2.5 rounded-lg border bg-surface-900/95 px-4 py-3 shadow-lg backdrop-blur-md",
        variantStyles[item.variant],
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <p className="flex-1 text-sm text-slate-200">{item.message}</p>
      <button
        onClick={() => dismiss(item.id)}
        className="shrink-0 text-slate-500 transition-colors hover:text-slate-300"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </motion.div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-80 flex-col gap-2">
      <AnimatePresence mode="popLayout">
        {toasts.map((t) => (
          <ToastItem key={t.id} item={t} />
        ))}
      </AnimatePresence>
    </div>
  );
}

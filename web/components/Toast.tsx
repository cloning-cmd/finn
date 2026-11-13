"use client";
import { AnimatePresence, motion } from "framer-motion";

export interface ToastState { id: string; text: string; onUndo?: () => void }

export default function Toast({ toast }: { toast: ToastState | null }) {
  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          key={toast.id}
          role="status"
          className="fixed inset-x-0 z-50 mx-auto flex w-[calc(100%-2rem)] max-w-md items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3 text-[13.5px] shadow-[0_8px_30px_rgb(0_0_0/0.3)]"
          style={{ bottom: "calc(env(safe-area-inset-bottom, 0px) + 88px)" }}
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }} transition={{ duration: 0.18 }}
        >
          <span className="text-fg">{toast.text}</span>
          {toast.onUndo && (
            <button onClick={toast.onUndo} className="ml-auto rounded-lg bg-accent/12 px-2.5 py-1 text-[12.5px] font-medium text-accent">Undo</button>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

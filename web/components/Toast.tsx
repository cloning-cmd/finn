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
          className="fixed inset-x-0 z-50 mx-auto flex w-[calc(100%-2rem)] max-w-md items-center gap-3 rounded-lg border border-line bg-card px-3 py-2 text-[13px] shadow-lg"
          style={{ bottom: "calc(env(safe-area-inset-bottom, 0px) + 4.25rem)" }}
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }} transition={{ duration: 0.18 }}
        >
          <span className="text-fg">{toast.text}</span>
          {toast.onUndo && (
            <button onClick={toast.onUndo} className="ml-auto rounded-full border border-line px-2.5 py-0.5 text-[12px] text-accent">Undo</button>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

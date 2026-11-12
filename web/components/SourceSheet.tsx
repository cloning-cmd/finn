"use client";
import { AnimatePresence, motion } from "framer-motion";
import type { Source } from "@/lib/types";

export interface SheetTarget { ticker: string; headline: string; sources: Source[] }

function host(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; }
}

/** Bottom sheet listing every source behind a card or claim (filing PDF, XBRL, transcript page, related filings). */
export default function SourceSheet({ card, focus, onClose }: { card: SheetTarget | null; focus?: string; onClose: () => void }) {
  const related: Source[] = card ? card.sources.filter((s) => s.id.startsWith("s_rel_")) : [];
  const primary: Source[] = card ? card.sources.filter((s) => !s.id.startsWith("s_rel_")) : [];
  return (
    <AnimatePresence>
      {card && (
        <>
          <motion.div key="bd" className="fixed inset-0 z-40 bg-black/50" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.section
            key="sheet"
            role="dialog"
            aria-label="Sources"
            className="fixed inset-x-0 bottom-0 z-50 mx-auto max-h-[80dvh] max-w-md overflow-y-auto rounded-t-2xl border border-line bg-card px-4 pb-8 pt-3"
            style={{ paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 2rem)" }}
            initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }} transition={{ type: "spring", stiffness: 420, damping: 38 }}
          >
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-line" />
            <header className="flex items-baseline gap-2">
              <span className="text-[13px] font-semibold">{card.ticker}</span>
              <span className="truncate text-[12.5px] text-muted">{card.headline}</span>
            </header>
            <ul className="mt-3 space-y-1.5">
              {primary.map((s) => (
                <li key={s.id}>
                  <a href={s.url} target="_blank" rel="noopener noreferrer"
                     className={`block rounded-lg border px-3 py-2 ${focus === s.id ? "border-accent" : "border-line"}`}>
                    <div className="text-[13px] text-fg">{s.label}{s.page ? <span className="text-muted"> · p.{s.page}</span> : null}</div>
                    <div className="truncate text-[11.5px] text-muted">{host(s.url)}</div>
                    {s.quote && <blockquote className="mt-1 border-l-2 border-line pl-2 text-[12px] text-muted">“{s.quote}”</blockquote>}
                  </a>
                </li>
              ))}
            </ul>
            {related.length > 0 && (
              <>
                <h3 className="mt-4 text-[11px] uppercase tracking-wide text-muted">{related.length} related filing{related.length > 1 ? "s" : ""} folded into this card</h3>
                <ul className="mt-1.5 space-y-1">
                  {related.map((s) => (
                    <li key={s.id}>
                      <a href={s.url} target="_blank" rel="noopener noreferrer" className="block rounded-lg border border-line px-3 py-1.5 text-[12.5px] text-fg">{s.label}</a>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {card.sources.length === 0 && <p className="mt-3 text-[12.5px] text-muted">No source attached.</p>}
          </motion.section>
        </>
      )}
    </AnimatePresence>
  );
}

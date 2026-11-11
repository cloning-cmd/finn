"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import type { Brief, Card, Chip } from "@/lib/types";
import { CATEGORY_LABEL } from "@/lib/types";
import { api } from "@/lib/api";
import CardView from "@/components/cards/CardView";
import SwipeCard, { type SwipeAction } from "@/components/cards/SwipeCard";
import SourceSheet from "@/components/SourceSheet";
import Toast, { type ToastState } from "@/components/Toast";

const WINDOWS = ["24h", "3d", "7d", "30d"] as const;
type Win = (typeof WINDOWS)[number];
const UNDO_MS = 4000;

export default function BriefScreen() {
  const params = useSearchParams();
  const router = useRouter();
  const fixture = params.get("fixture") === "1" || process.env.NEXT_PUBLIC_FIXTURE === "1";
  const [win, setWin] = useState<Win>("7d");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [openBuried, setOpenBuried] = useState<string | null>(null);
  const [gone, setGone] = useState<Record<string, SwipeAction>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [sheet, setSheet] = useState<{ card: Card; focus?: string } | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    setBrief(null); setErr(null); setGone({});
    api.brief(win, fixture).then(setBrief).catch((e) => setErr(String(e)));
  }, [win, fixture]);

  useEffect(() => () => { Object.values(timers.current).forEach(clearTimeout); }, []);

  // Swipe: hide the card now, send feedback after the undo window. Undo cancels the send and restores the card.
  const onSwipe = useCallback((card: Card, action: SwipeAction) => {
    setGone((g) => ({ ...g, [card.id]: action }));
    const category = card.type === "price_move" || card.type === "volume_spike" ? undefined : card.type;
    timers.current[card.id] = setTimeout(() => {
      api.feedback(card.id, action, card.ticker, category).catch(() => undefined);
      delete timers.current[card.id];
      setToast((t) => (t?.id === card.id ? null : t));
    }, UNDO_MS);
    setToast({
      id: card.id,
      text: action === "noted" ? `Noted · ${card.ticker}` : `Fewer ${category ? CATEGORY_LABEL[category as keyof typeof CATEGORY_LABEL] ?? category : "move"} cards for ${card.ticker}`,
      onUndo: () => {
        clearTimeout(timers.current[card.id]);
        delete timers.current[card.id];
        setGone((g) => { const n = { ...g }; delete n[card.id]; return n; });
        setToast(null);
      },
    });
  }, []);

  const onChip = useCallback((chip: Chip, card: Card) => {
    if (chip.action === "open_source") setSheet({ card, focus: chip.arg });
    else if (chip.action === "open_research") router.push(`/research?t=${chip.arg ?? card.ticker}`);
    else if (chip.action === "mute") onSwipe(card, "less");
    else if (chip.action === "ask") router.push(`/research?t=${card.ticker}&q=${encodeURIComponent(chip.arg ?? "")}`);
  }, [router, onSwipe]);

  const visible = brief ? brief.cards.filter((c) => !gone[c.id]) : [];
  const matter = brief ? brief.counts.lead + brief.counts.line : 0;
  const hidden = Object.keys(gone).length;

  return (
    <main>
      <header className="sticky top-0 z-30 -mx-4 border-b border-line bg-bg/95 px-4 pb-2 pt-3 backdrop-blur" style={{ top: "env(safe-area-inset-top, 0px)" }}>
        <div className="flex items-center gap-2">
          <h1 className="text-[17px] font-semibold tracking-tight">Brief</h1>
          <div className="ml-auto flex gap-1">
            {WINDOWS.map((w) => (
              <button key={w} onClick={() => setWin(w)} className={`rounded-full px-2.5 py-1 text-[12px] ${w === win ? "bg-fg text-bg" : "border border-line text-muted"}`}>{w}</button>
            ))}
          </div>
        </div>
        <p className="tabular mt-1 text-[12.5px] text-muted">
          {brief ? (<><span className="text-fg">{matter - hidden} matter</span> · {brief.counts.buried} buried · ~{brief.minutes_saved} min saved{brief.as_of === "fixture" && " · demo data"}</>) : err ? "API unreachable" : "…"}
        </p>
      </header>

      {err && <p className="mt-6 text-[13px] text-muted">Could not load the brief ({err}). Is the API running?</p>}

      {!brief && !err && (
        <div className="mt-3 space-y-2">{[0, 1, 2].map((i) => <div key={i} className="h-28 animate-pulse rounded-xl border border-line bg-card" />)}</div>
      )}

      {brief && (
        <>
          {visible.length === 0 && (
            <p className="mt-6 text-center text-[13px] text-muted">Nothing above the line in this window.</p>
          )}
          <section className="mt-3 space-y-2">
            <AnimatePresence initial={false}>
              {visible.map((c) => (
                <motion.div key={c.id} layout initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0, marginBottom: 0 }} transition={{ duration: 0.2 }}>
                  <SwipeCard onSwipe={(a) => onSwipe(c, a)}>
                    <CardView card={c} compact={c.tier === "line" && !expanded[c.id]} onChip={onChip} onExpand={(card) => setExpanded((e) => ({ ...e, [card.id]: true }))} />
                  </SwipeCard>
                </motion.div>
              ))}
            </AnimatePresence>
          </section>

          <section className="mt-8 text-center">
            <p className="text-[15px] font-medium">You&apos;re caught up.</p>
            <p className="mt-0.5 text-[12.5px] text-muted">{brief.counts.buried} routine filings buried below.</p>
          </section>

          <section className="mt-5 space-y-1.5">
            {brief.buried.map((g) => (
              <div key={g.category} className="rounded-lg border border-line">
                <button onClick={() => setOpenBuried(openBuried === g.category ? null : g.category)} className="flex w-full items-center px-3 py-2 text-[13px]">
                  <span className="text-muted">{CATEGORY_LABEL[g.category]}</span>
                  <span className="tabular ml-auto text-muted">{g.count}</span>
                </button>
                {openBuried === g.category && (
                  <ul className="border-t border-line px-3 py-1.5 text-[12.5px]">
                    {g.items.map((it) => (
                      <li key={it.id} className="flex gap-2 py-1"><span className="w-20 shrink-0 font-medium">{it.ticker}</span><span className="text-muted">{it.headline}</span></li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </section>
        </>
      )}

      <SourceSheet card={sheet?.card ?? null} focus={sheet?.focus} onClose={() => setSheet(null)} />
      <Toast toast={toast} />
    </main>
  );
}

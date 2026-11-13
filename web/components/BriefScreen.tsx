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
import { Button, Empty, Icon, PageHeader, Segmented, SectionLabel, Skeleton, TickerAvatar, cx, stripTicker } from "@/components/ui";

const WINDOWS = ["24h", "3d", "7d", "30d"] as const;
type Win = (typeof WINDOWS)[number];
const WIN_LABEL: Record<Win, string> = { "24h": "24H", "3d": "3D", "7d": "1W", "30d": "1M" };
const UNDO_MS = 4000;

function today(): string {
  return new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
}

export default function BriefScreen() {
  const params = useSearchParams();
  const router = useRouter();
  const fixture = params.get("fixture") === "1" || process.env.NEXT_PUBLIC_FIXTURE === "1";
  const initial = params.get("w");
  const [win, setWin] = useState<Win>(WINDOWS.includes(initial as Win) ? (initial as Win) : "7d");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const [openBuried, setOpenBuried] = useState<string | null>(null);
  const [gone, setGone] = useState<Record<string, SwipeAction>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [sheet, setSheet] = useState<{ card: Card; focus?: string } | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [nonce, setNonce] = useState(0);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    setBrief(null); setErr(null); setGone({}); setSlow(false);
    // The free API host sleeps when idle; say so instead of showing a blank skeleton for ~50 s.
    const t = setTimeout(() => setSlow(true), 4000);
    api.brief(win, fixture).then(setBrief).catch((e) => setErr(String(e))).finally(() => clearTimeout(t));
    return () => clearTimeout(t);
  }, [win, fixture, nonce]);

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
  const total = brief ? matter + brief.counts.buried : 0;

  return (
    <main>
      <PageHeader eyebrow={today()} title="Brief">
        <Segmented options={WINDOWS} value={win} onChange={setWin} labels={WIN_LABEL} />
      </PageHeader>

      {brief && (
        <section className="surface mt-1 grid grid-cols-3 divide-x divide-line rounded-2xl py-3">
          <div className="px-4">
            <div className="text-[11.5px] text-muted">Needs a look</div>
            <div className="tabular text-[22px] font-semibold tracking-tight">{Math.max(matter - hidden, 0)}</div>
          </div>
          <div className="px-4">
            <div className="text-[11.5px] text-muted">Filtered out</div>
            <div className="tabular text-[22px] font-semibold tracking-tight text-muted">{brief.counts.buried}<span className="text-[13px] font-normal text-faint">/{total}</span></div>
          </div>
          <div className="px-4">
            <div className="text-[11.5px] text-muted">Time saved</div>
            <div className="tabular text-[22px] font-semibold tracking-tight">{Math.round(brief.minutes_saved)}<span className="ml-0.5 text-[13px] font-normal text-muted">min</span></div>
          </div>
        </section>
      )}
      {brief?.as_of === "fixture" && <p className="mt-2 px-1 text-[12px] text-warn">Demo data</p>}

      {err && (
        <Empty icon={<Icon name="refresh" />} title="Could not load the brief" body="The API did not answer. It may be waking up; try again in a moment."
          action={<Button variant="secondary" size="sm" onClick={() => setNonce((n) => n + 1)}>Retry</Button>} />
      )}

      {!brief && !err && (
        <div className="mt-1 space-y-3">
          <Skeleton className="h-[74px]" />
          {slow && <p className="px-1 text-[12.5px] text-muted">Waking the server. The first load after a quiet spell takes up to a minute.</p>}
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-32" />)}
        </div>
      )}

      {brief && (
        <>
          {visible.length > 0 && <SectionLabel right={<span className="normal-case tracking-normal">Swipe right: noted · left: less</span>}>Needs a look</SectionLabel>}
          {visible.length === 0 && <Empty icon={<Icon name="check" />} title="Nothing needs a look" body="No filing or price move in this window crossed your thresholds." />}
          <section className="space-y-3">
            <AnimatePresence initial={false}>
              {visible.map((c) => (
                <motion.div key={c.id} layout initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0, marginTop: 0 }} transition={{ duration: 0.2 }}>
                  <SwipeCard onSwipe={(a) => onSwipe(c, a)}>
                    <CardView card={c} compact={c.tier === "line" && !expanded[c.id]} onChip={onChip} onExpand={(card) => setExpanded((e) => ({ ...e, [card.id]: true }))} />
                  </SwipeCard>
                </motion.div>
              ))}
            </AnimatePresence>
          </section>

          {visible.length > 0 && (
            <div className="mt-8 flex flex-col items-center text-center">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-up/12 text-up"><Icon name="check" size={20} strokeWidth={2.2} /></span>
              <p className="mt-2 text-[15px] font-semibold">You&apos;re caught up</p>
              <p className="mt-0.5 text-[12.5px] text-muted">{brief.counts.buried} routine filings were filtered out below.</p>
            </div>
          )}

          {brief.buried.length > 0 && (
            <>
              <SectionLabel right={brief.counts.buried}>Filtered out</SectionLabel>
              <ul className="surface divide-y divide-line overflow-hidden rounded-2xl">
                {brief.buried.map((g) => {
                  const open = openBuried === g.category;
                  return (
                    <li key={g.category}>
                      <button onClick={() => setOpenBuried(open ? null : g.category)} aria-expanded={open}
                        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2">
                        <span className="text-[13.5px]">{CATEGORY_LABEL[g.category]}</span>
                        <span className="tabular ml-auto rounded-md bg-surface-2 px-1.5 py-0.5 text-[11.5px] text-muted">{g.count}</span>
                        <Icon name="down" size={16} className={cx("text-faint transition-transform", open && "rotate-180")} />
                      </button>
                      {open && (
                        <ul className="space-y-2.5 bg-surface-2/50 px-4 py-3">
                          {g.items.map((it) => (
                            <li key={it.id} className="flex items-center gap-2.5">
                              <TickerAvatar ticker={it.ticker} size={24} />
                              <span className="w-24 shrink-0 truncate text-[12.5px] font-medium">{it.ticker}</span>
                              <span className="truncate text-[12.5px] text-muted">{stripTicker(it.headline, it.ticker)}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </>
      )}

      <SourceSheet card={sheet?.card ?? null} focus={sheet?.focus} onClose={() => setSheet(null)} />
      <Toast toast={toast} />
    </main>
  );
}

"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Alert, Card, Chip } from "@/lib/types";
import { api } from "@/lib/api";
import CardView from "@/components/cards/CardView";
import SourceSheet from "@/components/SourceSheet";
import { fmtWhen } from "@/lib/format";
import { Button, Empty, Icon, PageHeader, SectionLabel, Skeleton, TickerAvatar, stripTicker } from "@/components/ui";

function dayLabel(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  if (same(d, today)) return "Today";
  const y = new Date(today); y.setDate(today.getDate() - 1);
  if (same(d, y)) return "Yesterday";
  return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

export default function AlertsScreen() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sheet, setSheet] = useState<{ card: Card; focus?: string } | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [demo, setDemo] = useState(false);
  const [date, setDate] = useState(() => { const d = new Date(); d.setDate(d.getDate() - 1); return d.toISOString().slice(0, 10); });
  const [replay, setReplay] = useState<string | null>(null);
  const [firing, setFiring] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(() => api.alerts(100).then((a) => { setAlerts(a); setErr(null); }).catch((e) => setErr(String(e))), []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  const onChip = useCallback((chip: Chip, card: Card) => {
    if (chip.action === "open_source") setSheet({ card, focus: chip.arg });
    else if (chip.action === "open_research") router.push(`/research?t=${chip.arg ?? card.ticker}`);
    else if (chip.action === "ask") router.push(`/research?t=${card.ticker}&q=${encodeURIComponent(chip.arg ?? "")}`);
  }, [router]);

  const onReplay = async () => {
    setReplay(null); setFiring(true);
    try {
      const r = await api.replay(date, 3);
      setReplay(r.queued ? `Replaying ${r.queued} alert${r.queued > 1 ? "s" : ""} from ${date}, one every 3 seconds.` : `No alert-worthy cards on ${date}.`);
      if (timer.current) clearInterval(timer.current);
      let n = 0;
      timer.current = setInterval(() => { void load(); if (++n >= Math.max(3, r.queued + 1)) { if (timer.current) clearInterval(timer.current); } }, 3000);
    } catch (e) { setReplay(`Replay failed: ${e instanceof Error ? e.message : String(e)}`); } finally { setFiring(false); }
  };

  const groups: { day: string; items: Alert[] }[] = [];
  for (const a of alerts ?? []) {
    const day = dayLabel(a.fired_at);
    const g = groups[groups.length - 1];
    if (g && g.day === day) g.items.push(a); else groups.push({ day, items: [a] });
  }
  const pushed = alerts?.filter((a) => a.delivered).length ?? 0;

  return (
    <main>
      <PageHeader title="Alerts" eyebrow={alerts ? `${alerts.length} fired · ${pushed} pushed to devices` : err ? "API unreachable" : "Loading"}
        right={<Button size="sm" variant={demo ? "primary" : "secondary"} onClick={() => setDemo((d) => !d)}><Icon name="play" size={13} />Replay</Button>} />

      {demo && (
        <section className="surface mt-1 rounded-2xl p-4">
          <div className="text-[14px] font-semibold">Replay a day</div>
          <p className="mt-0.5 text-[12.5px] text-muted">Re-fires that day&apos;s alerts as live notifications, one every 3 seconds.</p>
          <div className="mt-3 flex items-center gap-2">
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Day to replay"
              className="h-10 flex-1 rounded-xl bg-surface-2 px-3 text-[13.5px] outline-none focus:ring-2 focus:ring-accent/50" />
            <Button onClick={onReplay} disabled={firing}>{firing ? "Starting" : "Fire"}</Button>
          </div>
          {replay && <p className="mt-2 text-[12.5px] text-muted">{replay}</p>}
        </section>
      )}

      {err && <Empty icon={<Icon name="refresh" />} title="Could not load alerts" body="The API did not answer. It may be waking up." action={<Button size="sm" variant="secondary" onClick={() => void load()}>Retry</Button>} />}
      {alerts && alerts.length === 0 && <Empty icon={<Icon name="bell" />} title="No alerts yet" body="Rules run after every filings and price update. Matches land here and on your phone." />}
      {!alerts && !err && <div className="mt-2 space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24" />)}</div>}

      {groups.map((g) => (
        <section key={g.day}>
          <SectionLabel right={g.items.length}>{g.day}</SectionLabel>
          <ul className="surface divide-y divide-line overflow-hidden rounded-2xl">
            {g.items.map((a) => (
              <li key={a.id}>
                {expanded[a.id] ? (
                  <div className="bg-surface-2/40 p-2">
                    <button onClick={() => setExpanded((e) => ({ ...e, [a.id]: false }))} className="mb-1.5 flex w-full items-center gap-2 px-2 pt-1 text-[12px] text-muted">
                      <Icon name="bell" size={13} className="text-accent" /><span className="font-medium text-fg/90">{a.rule_name}</span>
                      <span className="tabular ml-auto">{fmtWhen(a.fired_at)}{a.delivered ? " · pushed" : ""}</span>
                      <Icon name="down" size={14} className="rotate-180" />
                    </button>
                    <CardView card={a.card} onChip={onChip} />
                  </div>
                ) : (
                  <button onClick={() => setExpanded((e) => ({ ...e, [a.id]: true }))} className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2">
                    <TickerAvatar ticker={a.card.ticker} size={34} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 text-[12px]">
                        <span className="text-[13px] font-semibold">{a.card.ticker}</span>
                        <span className="truncate text-muted">{a.rule_name}</span>
                        <span className="tabular ml-auto shrink-0 text-faint">{fmtWhen(a.fired_at)}</span>
                      </div>
                      <div className="mt-0.5 line-clamp-2 text-[13.5px] leading-snug">{stripTicker(a.card.headline, a.card.ticker)}</div>
                      {a.delivered && <div className="mt-1 text-[11px] text-up">Pushed</div>}
                    </div>
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}

      <SourceSheet card={sheet?.card ?? null} focus={sheet?.focus} onClose={() => setSheet(null)} />
    </main>
  );
}

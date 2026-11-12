"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Alert, Card, Chip } from "@/lib/types";
import { api } from "@/lib/api";
import CardView from "@/components/cards/CardView";
import SourceSheet from "@/components/SourceSheet";
import { fmtWhen } from "@/lib/format";

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
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(() => api.alerts(100).then(setAlerts).catch((e) => setErr(String(e))), []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  const onChip = useCallback((chip: Chip, card: Card) => {
    if (chip.action === "open_source") setSheet({ card, focus: chip.arg });
    else if (chip.action === "open_research") router.push(`/research?t=${chip.arg ?? card.ticker}`);
    else if (chip.action === "ask") router.push(`/research?t=${card.ticker}&q=${encodeURIComponent(chip.arg ?? "")}`);
  }, [router]);

  const onReplay = async () => {
    setReplay(null);
    try {
      const r = await api.replay(date, 3);
      setReplay(r.queued ? `Replaying ${r.queued} alert${r.queued > 1 ? "s" : ""} from ${date}, one every 3 s.` : `No alert-worthy cards on ${date}.`);
      if (timer.current) clearInterval(timer.current);
      let n = 0;
      timer.current = setInterval(() => { void load(); if (++n >= Math.max(3, r.queued + 1)) { if (timer.current) clearInterval(timer.current); } }, 3000);
    } catch (e) { setReplay(`Replay failed: ${e instanceof Error ? e.message : String(e)}`); }
  };

  const groups: { day: string; items: Alert[] }[] = [];
  for (const a of alerts ?? []) {
    const day = dayLabel(a.fired_at);
    const g = groups[groups.length - 1];
    if (g && g.day === day) g.items.push(a); else groups.push({ day, items: [a] });
  }

  return (
    <main>
      <header className="sticky top-0 z-30 -mx-4 border-b border-line bg-bg/95 px-4 pb-2 pt-3 backdrop-blur" style={{ top: "env(safe-area-inset-top, 0px)" }}>
        <div className="flex items-center">
          <h1 className="text-[17px] font-semibold tracking-tight">Alerts</h1>
          <button onClick={() => setDemo((d) => !d)} className="ml-auto rounded-full border border-line px-2.5 py-1 text-[12px] text-muted" aria-expanded={demo}>Demo</button>
        </div>
        <p className="mt-1 text-[12.5px] text-muted">{alerts ? `${alerts.length} fired · ${alerts.filter((a) => a.delivered).length} pushed` : err ? "API unreachable" : "…"}</p>
        {demo && (
          <div className="mt-2 flex items-center gap-2 rounded-xl border border-dashed border-line p-2">
            <span className="text-[12px] text-muted">Replay a day</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="rounded-md border border-line bg-card px-2 py-0.5 text-[12px]" />
            <button onClick={onReplay} className="ml-auto rounded-full bg-fg px-3 py-1 text-[12px] text-bg">Fire</button>
          </div>
        )}
        {replay && <p className="mt-1 text-[12px] text-muted">{replay}</p>}
      </header>

      {err && <p className="mt-6 text-[13px] text-muted">Could not load alerts ({err}).</p>}
      {alerts && alerts.length === 0 && <p className="mt-6 text-center text-[13px] text-muted">No alerts yet. Rules run on every ingest.</p>}

      {groups.map((g) => (
        <section key={g.day} className="mt-4">
          <h2 className="text-[11px] uppercase tracking-wide text-muted">{g.day}</h2>
          <ul className="mt-1.5 space-y-2">
            {g.items.map((a) => (
              <li key={a.id}>
                <div className="mb-0.5 flex items-baseline gap-2 px-1 text-[11.5px] text-muted">
                  <span>{a.rule_name}</span>
                  <span className="tabular ml-auto">{fmtWhen(a.fired_at)}{a.delivered ? " · pushed" : ""}</span>
                </div>
                <CardView card={a.card} compact={!expanded[a.id]} onChip={onChip} onExpand={() => setExpanded((e) => ({ ...e, [a.id]: true }))} />
              </li>
            ))}
          </ul>
        </section>
      ))}

      {!alerts && !err && <div className="mt-3 space-y-2">{[0, 1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-xl border border-line bg-card" />)}</div>}
      <SourceSheet card={sheet?.card ?? null} focus={sheet?.focus} onClose={() => setSheet(null)} />
    </main>
  );
}

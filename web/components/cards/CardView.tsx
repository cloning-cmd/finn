"use client";
import type { Card, Chip, ResultsPayload, PeoplePayload, MovePayload, GenericPayload } from "@/lib/types";
import { CATEGORY_LABEL } from "@/lib/types";
import { fmtCr, fmtPct, fmtBps, fmtX, fmtVol, fmtWhen, dirClass } from "@/lib/format";
import Sparkline from "@/components/charts/Sparkline";

const STATUS_LABEL: Record<string, string> = { kept: "Kept", on_track: "On track", missed: "Missed", revised_down: "Revised down", quietly_dropped: "Quietly dropped", too_early: "Too early" };

function TypeTag({ card }: { card: Card }) {
  const label = card.type === "price_move" ? "Move" : card.type === "volume_spike" ? "Volume" : CATEGORY_LABEL[card.type as keyof typeof CATEGORY_LABEL] ?? card.type;
  return <span className="rounded-sm bg-line px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted">{label}</span>;
}

function Results({ p }: { p: ResultsPayload }) {
  return (
    <div className="mt-2">
      <table className="w-full text-[13px] tabular">
        <thead>
          <tr className="text-[10px] uppercase tracking-wide text-muted">
            <th className="pb-1 text-left font-normal">{p.unit} · {p.basis}</th>
            <th className="pb-1 text-right font-normal">Value</th>
            <th className="pb-1 text-right font-normal">QoQ</th>
            <th className="pb-1 text-right font-normal">YoY</th>
          </tr>
        </thead>
        <tbody>
          {p.metrics.map((m) => (
            <tr key={m.name} className="border-t border-line/60">
              <td className="py-1 pr-2 text-fg">{m.name}</td>
              <td className="py-1 text-right">{fmtCr(m.value)}</td>
              <td className={`py-1 text-right ${dirClass(m.qoq_pct)}`}>{fmtPct(m.qoq_pct)}</td>
              <td className={`py-1 text-right ${dirClass(m.yoy_pct)}`}>{fmtPct(m.yoy_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted">
        {p.margins?.map((m) => (
          <span key={m.name} className="tabular">{m.name} {m.pct.toFixed(1)}% <span className={dirClass(m.qoq_bps)}>{fmtBps(m.qoq_bps)} QoQ</span></span>
        ))}
        {p.vs_guidance && (
          <span className={`rounded-full px-2 py-0.5 text-[11px] status-${p.vs_guidance.status}`}>{STATUS_LABEL[p.vs_guidance.status]} · {p.vs_guidance.text}</span>
        )}
        <span className="ml-auto rounded-sm border border-line px-1 text-[10px] uppercase">{p.extraction === "xbrl" ? "XBRL" : p.extraction === "pdf_table" ? "PDF" : "LLM"}</span>
      </div>
    </div>
  );
}

function People({ p }: { p: PeoplePayload }) {
  return (
    <div className="mt-2 text-[13px]">
      <div className="text-fg">
        {p.role}: {p.outgoing?.name ?? "—"} <span className="text-muted">→</span> {p.incoming?.name ?? "—"}
        {p.effective_date && <span className="text-muted"> · from {p.effective_date}</span>}
      </div>
      {p.incoming && (
        <ul className="mt-1.5 space-y-0.5 text-muted">
          {p.incoming.bio_lines.map((l, i) => <li key={i} className="flex gap-2"><span className="text-line">·</span><span>{l}</span></li>)}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {p.flags.map((f) => <span key={f} className="rounded-sm bg-warn/15 px-1.5 py-0.5 text-[11px] text-warn">{f}</span>)}
        {p.incoming?.bio_sources.map((s) => <span key={s.id} className="rounded-sm border border-line px-1.5 py-0.5 text-[11px] text-muted">{s.label}</span>)}
      </div>
    </div>
  );
}

function Move({ p, card }: { p: MovePayload; card: Card }) {
  return (
    <div className="mt-2">
      <div className="flex items-center gap-3">
        {p.sparkline && <Sparkline values={p.sparkline} className="h-9 w-28" positive={p.change_pct >= 0} />}
        <div className="tabular text-[13px]">
          <div><span className="text-fg">{fmtCr(p.close)}</span> <span className={dirClass(p.change_pct)}>{fmtPct(p.change_pct)}</span></div>
          <div className="text-muted">z {p.z.toFixed(1)} · vol {fmtVol(p.volume)} ({fmtX(p.vol_multiple)})</div>
        </div>
      </div>
      <div className="mt-2 text-[12px]">
        {card.unexplained ? (
          <span className="rounded-sm bg-warn/15 px-1.5 py-0.5 text-warn">Unexplained · no filing in ±48h</span>
        ) : (
          p.window_filings.map((f) => <span key={f.id} className="text-muted">Explained by: <span className="text-fg">{f.headline}</span></span>)
        )}
      </div>
    </div>
  );
}

function Generic({ p }: { p: GenericPayload }) {
  if (!p.fields) return null;
  return (
    <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[12px]">
      {Object.entries(p.fields).map(([k, v]) => (<><dt key={k + "k"} className="text-muted">{k}</dt><dd key={k + "v"} className="tabular text-fg">{v}</dd></>))}
    </dl>
  );
}

export default function CardView({ card, compact = false, onChip, onExpand }: {
  card: Card; compact?: boolean; onChip?: (chip: Chip, card: Card) => void; onExpand?: (card: Card) => void;
}) {
  const p = card.payload;
  const related = card.sources.filter((s) => s.id.startsWith("s_rel_")).length;
  const chips: Chip[] = related > 0 ? [{ label: `+${related} related`, action: "open_source", arg: "related" }, ...card.chips] : card.chips;
  return (
    <article className={`rounded-xl border border-line bg-card ${compact ? "px-3 py-2.5" : "p-3.5"}`} onClick={compact && onExpand ? () => onExpand(card) : undefined}>
      <header className="flex items-center gap-2 text-[11px] text-muted">
        <span className="font-semibold text-fg">{card.ticker}</span>
        <TypeTag card={card} />
        {compact && related > 0 && <span className="tabular">+{related}</span>}
        <span className="ml-auto tabular">{fmtWhen(card.ts)}</span>
        <span className="tabular rounded-sm bg-accent/15 px-1.5 text-accent" title="priority">{Math.round(card.priority)}</span>
      </header>
      <h2 className={`mt-1 ${compact ? "text-[14px]" : "text-[15px]"} font-medium leading-snug text-fg`}>{card.headline}</h2>
      {card.one_liner && !compact && <p className="mt-0.5 text-[12.5px] leading-snug text-muted">{card.one_liner}</p>}
      {!compact && (
        <>
          {card.type === "results" && <Results p={p as ResultsPayload} />}
          {card.type === "management_change" && <People p={p as PeoplePayload} />}
          {(card.type === "price_move" || card.type === "volume_spike") && <Move p={p as MovePayload} card={card} />}
          {!["results", "management_change", "price_move", "volume_spike"].includes(card.type) && <Generic p={p as GenericPayload} />}
          {chips.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {chips.map((c, i) => (
                <button key={i} onClick={() => onChip?.(c, card)} className="rounded-full border border-line px-2.5 py-1 text-[12px] text-fg active:bg-line">{c.label}</button>
              ))}
            </div>
          )}
        </>
      )}
    </article>
  );
}

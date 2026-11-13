"use client";
import { Component, type ReactNode } from "react";
import type { Card, Chip, ResultsPayload, PeoplePayload, MovePayload, GenericPayload } from "@/lib/types";
import { CATEGORY_LABEL } from "@/lib/types";
import { fmtCr, fmtPct, fmtBps, fmtX, fmtVol, fmtWhen, dirClass } from "@/lib/format";
import Sparkline from "@/components/charts/Sparkline";
import { Badge, PersonAvatar, TickerAvatar, cx, stripTicker } from "@/components/ui";

const STATUS_LABEL: Record<string, string> = { kept: "Kept", on_track: "On track", missed: "Missed", revised_down: "Revised down", quietly_dropped: "Quietly dropped", too_early: "Too early" };
const CHANGE_LABEL: Record<string, string> = { appointment: "Appointed", resignation: "Resigned", retirement: "Retiring", cessation: "Stepping down" };

function typeLabel(card: Card): string {
  if (card.type === "price_move") return "Price move";
  if (card.type === "volume_spike") return "Volume";
  return CATEGORY_LABEL[card.type as keyof typeof CATEGORY_LABEL] ?? card.type;
}

function Results({ p }: { p: ResultsPayload }) {
  return (
    <div className="mt-3">
      <div className="grid grid-cols-2 gap-2">
        {(p.metrics ?? []).map((m) => (
          <div key={m.name} className="rounded-xl bg-surface-2 px-3 py-2.5">
            <div className="text-[11.5px] text-muted">{m.name}</div>
            <div className="tabular mt-0.5 text-[16px] font-semibold tracking-tight">₹{fmtCr(m.value)}<span className="ml-1 text-[11px] font-normal text-muted">Cr</span></div>
            <div className="tabular mt-0.5 flex gap-2 text-[11.5px]">
              <span className={dirClass(m.yoy_pct)}>{fmtPct(m.yoy_pct)} YoY</span>
              <span className={cx("opacity-80", dirClass(m.qoq_pct))}>{fmtPct(m.qoq_pct)} QoQ</span>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[12px] text-muted">
        {p.margins?.map((m) => (
          <span key={m.name} className="tabular">{m.name} <span className="text-fg">{m.pct.toFixed(1)}%</span> <span className={dirClass(m.qoq_bps)}>{fmtBps(m.qoq_bps)}</span></span>
        ))}
        {p.vs_guidance && <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-medium status-${p.vs_guidance.status}`}>{STATUS_LABEL[p.vs_guidance.status]} · {p.vs_guidance.text}</span>}
        <span className="ml-auto text-[11px] text-faint">{p.basis} · {p.extraction === "xbrl" ? "XBRL" : p.extraction === "pdf_table" ? "PDF" : "LLM"}</span>
      </div>
    </div>
  );
}

function People({ p }: { p: PeoplePayload }) {
  const rows: { name: string; label: string; tone: "up" | "down" }[] = [];
  if (p.outgoing) rows.push({ name: p.outgoing.name, label: p.change === "appointment" ? "Outgoing" : CHANGE_LABEL[p.change] ?? "Leaving", tone: "down" });
  if (p.incoming) rows.push({ name: p.incoming.name, label: "Appointed", tone: "up" });
  return (
    <div className="mt-3">
      <div className="rounded-xl bg-surface-2 p-3">
        <div className="text-[11.5px] text-muted">{p.role}{p.effective_date && <> · from {new Date(p.effective_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</>}</div>
        <ul className="mt-2 space-y-2">
          {rows.map((r) => (
            <li key={r.label + r.name} className="flex items-center gap-2.5">
              <PersonAvatar name={r.name} size={28} />
              <span className="text-[13.5px] font-medium">{r.name}</span>
              <Badge tone={r.tone} className="ml-auto">{r.label}</Badge>
            </li>
          ))}
        </ul>
        {p.incoming && (p.incoming.bio_lines ?? []).length > 0 && (
          <ul className="mt-3 space-y-1 border-t border-line pt-2.5 text-[12.5px] leading-snug text-muted">
            {(p.incoming.bio_lines ?? []).map((l, i) => <li key={i} className="flex gap-2"><span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-faint" />{l}</li>)}
          </ul>
        )}
      </div>
      {((p.flags ?? []).length > 0 || (p.incoming?.bio_sources ?? []).length > 0) && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {(p.flags ?? []).map((f) => <Badge key={f} tone="warn">{f}</Badge>)}
          {(p.incoming?.bio_sources ?? []).map((s) => <Badge key={s.id}>{s.label}</Badge>)}
        </div>
      )}
    </div>
  );
}

function Move({ p, card }: { p: MovePayload; card: Card }) {
  return (
    <div className="mt-3">
      <div className="flex items-end gap-4 rounded-xl bg-surface-2 px-3 py-2.5">
        <div className="tabular">
          <div className={cx("text-[20px] font-semibold tracking-tight", dirClass(p.change_pct))}>{fmtPct(p.change_pct)}</div>
          <div className="text-[11.5px] text-muted">close ₹{fmtCr(p.close)}</div>
        </div>
        {p.sparkline && p.sparkline.length > 1 && <Sparkline values={p.sparkline} className="h-10 flex-1" positive={p.change_pct >= 0} />}
        <div className="tabular ml-auto text-right text-[11.5px] text-muted">
          <div><span className="text-fg">{p.z.toFixed(1)}σ</span> move</div>
          <div><span className="text-fg">{fmtX(p.vol_multiple)}</span> vol · {fmtVol(p.volume)}</div>
        </div>
      </div>
      <div className="mt-2 text-[12.5px]">
        {card.unexplained ? (
          <Badge tone="warn">Unexplained · no filing within 48h</Badge>
        ) : (
          (p.window_filings ?? []).slice(0, 2).map((f) => <div key={f.id} className="truncate text-muted">Explained by <span className="text-fg">{f.headline}</span></div>)
        )}
      </div>
    </div>
  );
}

function Generic({ p }: { p: GenericPayload }) {
  if (!p.fields) return null;
  return (
    <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-xl bg-surface-2 px-3 py-2.5 text-[12.5px]">
      {Object.entries(p.fields).map(([k, v]) => (
        <div key={k} className="contents"><dt className="text-muted">{k}</dt><dd className="tabular text-fg">{v}</dd></div>
      ))}
    </dl>
  );
}

// One malformed payload must cost one card body, not the whole Brief.
class BodyBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e: unknown) { console.error("card body failed to render", e); }
  render() { return this.state.failed ? null : this.props.children; }
}

// The card type says what the filing is; the payload says what enrichment produced. A management change whose
// attachment could not be read, or a "results" filing the XBRL guard rejected, still carries the generic payload,
// so the renderer is chosen from the payload's shape and falls back to the generic view.
function payloadKind(card: Card): "results" | "people" | "move" | "generic" {
  const p = (card.payload ?? {}) as unknown as Record<string, unknown>;
  if (card.type === "results" && Array.isArray(p.metrics)) return "results";
  if (card.type === "management_change" && typeof p.change === "string" && typeof p.role === "string") return "people";
  if ((card.type === "price_move" || card.type === "volume_spike") && typeof p.close === "number" && typeof p.z === "number") return "move";
  return "generic";
}

export default function CardView({ card, compact = false, onChip, onExpand }: {
  card: Card; compact?: boolean; onChip?: (chip: Chip, card: Card) => void; onExpand?: (card: Card) => void;
}) {
  const p = card.payload;
  const kind = payloadKind(card);
  const related = (card.sources ?? []).filter((s) => s.id.startsWith("s_rel_")).length;
  const chips: Chip[] = related > 0 ? [{ label: `${related} related`, action: "open_source", arg: "related" }, ...(card.chips ?? [])] : (card.chips ?? []);
  const lead = card.tier === "lead";
  return (
    <article className={cx("surface rounded-2xl", compact ? "px-4 py-3" : "p-4", compact && onExpand && "cursor-pointer")}
      onClick={compact && onExpand ? () => onExpand(card) : undefined}>
      <header className="flex items-center gap-3">
        <TickerAvatar ticker={card.ticker} size={compact ? 32 : 36} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="truncate text-[13.5px] font-semibold tracking-tight">{card.ticker}</span>
            {lead && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" title={`Priority ${Math.round(card.priority)}`} aria-label="lead" />}
          </div>
          <div className="truncate text-[11.5px] text-muted">{card.company && card.company !== card.ticker ? card.company : typeLabel(card)}</div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Badge>{typeLabel(card)}</Badge>
          <span className="tabular text-[11px] text-faint" title={`Priority ${Math.round(card.priority)}`}>{fmtWhen(card.ts)}{related > 0 && compact ? ` · +${related}` : ""}</span>
        </div>
      </header>
      <h3 className={cx("mt-2.5 font-medium leading-snug tracking-[-0.005em] text-fg", compact ? "text-[14px]" : "text-[15.5px]")}>{stripTicker(card.headline, card.ticker)}</h3>
      {card.one_liner && !compact && <p className="mt-1 text-[13px] leading-snug text-muted">{card.one_liner}</p>}
      {!compact && (
        <>
          <BodyBoundary>
            {kind === "results" && <Results p={p as ResultsPayload} />}
            {kind === "people" && <People p={p as PeoplePayload} />}
            {kind === "move" && <Move p={p as MovePayload} card={card} />}
            {kind === "generic" && <Generic p={p as GenericPayload} />}
          </BodyBoundary>
          {chips.length > 0 && (
            <div className="-mx-1 mt-3 flex flex-wrap gap-1.5 border-t border-line pt-3">
              {chips.map((c, i) => (
                <button key={i} onClick={(e) => { e.stopPropagation(); onChip?.(c, card); }}
                  className={cx("rounded-lg px-2.5 py-1.5 text-[12.5px] font-medium transition-colors",
                    c.action === "open_research" ? "bg-accent/12 text-accent hover:bg-accent/20" : "text-muted hover:bg-surface-2 hover:text-fg")}>
                  {c.label}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </article>
  );
}

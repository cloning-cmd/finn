"use client";
import { useState } from "react";
import type { Claim, PromiseRec, PromiseStatus, Source } from "@/lib/types";
import { Icon, cx } from "@/components/ui";
import ClaimList, { type OpenSources } from "./ClaimList";

export const STATUS_LABEL: Record<PromiseStatus, string> = {
  kept: "Kept", on_track: "On track", missed: "Missed", revised_down: "Revised down", quietly_dropped: "Quietly dropped", too_early: "Too early",
};
const STATUS_BG: Record<PromiseStatus, string> = {
  kept: "bg-up", on_track: "bg-accent", missed: "bg-down", revised_down: "bg-warn", quietly_dropped: "bg-down/60", too_early: "bg-line-strong",
};
const STATUS_PILL: Record<PromiseStatus, string> = {
  kept: "bg-up/12 text-up", on_track: "bg-accent/12 text-accent", missed: "bg-down/12 text-down", revised_down: "bg-warn/14 text-warn",
  quietly_dropped: "bg-down/10 text-down", too_early: "bg-surface-2 text-muted",
};
const METRIC_LABEL: Record<string, string> = {
  revenue_growth: "Revenue growth", ebitda_margin: "Operating margin", pat: "Profit", capex: "Capex", net_debt: "Net debt",
  order_book: "Order book", capacity: "Capacity", launch: "Launches", headcount: "Hiring", tax_rate: "Tax rate", payout: "Payout",
  attrition: "Attrition", onsite_mix: "Onsite mix", other: "Other",
};
const METRIC_ORDER = ["revenue_growth", "ebitda_margin", "pat", "capex", "net_debt", "order_book", "capacity", "headcount", "tax_rate", "payout"];
const ORDER: PromiseStatus[] = ["kept", "on_track", "missed", "revised_down", "quietly_dropped", "too_early"];
const STANCE: Record<string, string> = { reiterated: "reiterated", raised: "raised", lowered: "lowered", absent: "not mentioned" };
const PER_GROUP = 2;

function PromiseRow({ p, onOpen }: { p: PromiseRec; onOpen: (p: PromiseRec) => void }) {
  return (
    <li>
      <button onClick={() => onOpen(p)} className="w-full px-4 py-3 text-left transition-colors hover:bg-surface-2">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-[13.5px] font-medium leading-snug">{p.target_text}</div>
            <div className="mt-0.5 text-[12px] text-muted">for {p.period} · said {p.said_in}{p.speaker ? ` · ${p.speaker.replace(" [mgmt]", "")}` : ""}{!p.hard && " · soft"}</div>
          </div>
          <span className={cx("shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium", STATUS_PILL[p.status])}>{STATUS_LABEL[p.status]}</span>
        </div>
        {p.later_mentions.length > 0 && (
          <div className="no-scrollbar mt-2 flex gap-1.5 overflow-x-auto">
            {p.later_mentions.map((m, i) => (
              <span key={i} className={cx("shrink-0 rounded-md border border-line px-1.5 py-0.5 text-[11px]",
                m.stance === "lowered" ? "text-down" : m.stance === "raised" ? "text-up" : "text-muted")}>
                {m.call} · {STANCE[m.stance] ?? m.stance}
              </span>
            ))}
          </div>
        )}
        <div className="mt-2 text-[12.5px] leading-snug">
          {p.actual_text ? <><span className="text-muted">Actual </span>{p.actual_text}</> : <span className="text-faint">Actual not yet reported</span>}
        </div>
      </button>
    </li>
  );
}

/** Promise Ledger: a status bar with counts, then one collapsible group per metric. Tap a promise for its quote. */
export default function Ledger({ ledger, sources, onOpen }: {
  ledger: { summary: Record<PromiseStatus, number>; promises: PromiseRec[]; narrative: Claim[] };
  sources: Source[]; onOpen: OpenSources;
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const total = ledger.promises.length;
  // One group per metric; hard promises first, newest call first inside a group.
  const groups = Object.entries(ledger.promises.reduce<Record<string, PromiseRec[]>>((acc, p) => { (acc[p.metric] ||= []).push(p); return acc; }, {}))
    .map(([m, items]) => [m, [...items].sort((a, b) => Number(b.hard) - Number(a.hard) || b.said_in.localeCompare(a.said_in))] as [string, PromiseRec[]])
    .sort((a, b) => (METRIC_ORDER.indexOf(a[0]) + 1 || 99) - (METRIC_ORDER.indexOf(b[0]) + 1 || 99) || b[1].length - a[1].length);
  const openQuote = (p: PromiseRec) => {
    const srcs: Source[] = [{ ...p.source, label: `${p.speaker ? p.speaker.replace(" [mgmt]", "") + " · " : ""}${p.said_in}`, quote: p.quote }];
    if (p.actual_source) srcs.push({ ...p.actual_source, label: `Actual: ${p.actual_source.label}` });
    onOpen(`${p.metric}: ${p.target_text}`, srcs, p.source.id);
  };
  const counted = ORDER.filter((s) => (ledger.summary[s] ?? 0) > 0);
  const resolved = (ledger.summary.kept ?? 0) + (ledger.summary.missed ?? 0) + (ledger.summary.revised_down ?? 0) + (ledger.summary.quietly_dropped ?? 0);

  return (
    <div className="space-y-4">
      <section className="surface rounded-2xl p-4">
        <div className="flex items-baseline gap-2">
          <h2 className="text-[15px] font-semibold tracking-tight">Promise ledger</h2>
          <span className="tabular ml-auto text-[12.5px] text-muted">{total} tracked{resolved > 0 && ` · ${ledger.summary.kept ?? 0} of ${resolved} kept`}</span>
        </div>
        {total === 0 ? (
          <p className="mt-2 text-[13px] text-muted">No quantified guidance found in the transcripts on file.</p>
        ) : (
          <>
            <div className="mt-3 flex h-2 gap-0.5 overflow-hidden rounded-full">
              {counted.map((s) => <div key={s} className={STATUS_BG[s]} style={{ flexGrow: ledger.summary[s] }} title={`${STATUS_LABEL[s]} ${ledger.summary[s]}`} />)}
            </div>
            <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12.5px] sm:grid-cols-3">
              {counted.map((s) => (
                <li key={s} className="flex items-center gap-2">
                  <span className={cx("h-2 w-2 rounded-full", STATUS_BG[s])} aria-hidden="true" />
                  <span className="text-muted">{STATUS_LABEL[s]}</span>
                  <span className="tabular ml-auto font-medium">{ledger.summary[s]}</span>
                </li>
              ))}
            </ul>
          </>
        )}
        {ledger.narrative.length > 0 && <div className="mt-4 border-t border-line pt-4"><ClaimList claims={ledger.narrative} sources={sources} onOpen={onOpen} dense /></div>}
      </section>

      {groups.map(([metric, items]) => {
        const all = open[metric];
        const shown = all ? items : items.slice(0, PER_GROUP);
        return (
          <section key={metric} className="surface overflow-hidden rounded-2xl">
            <div className="flex items-center gap-2 px-4 pb-1 pt-3.5">
              <h3 className="text-[13.5px] font-semibold">{METRIC_LABEL[metric] ?? metric.replace(/_/g, " ")}</h3>
              <span className="flex gap-1" aria-hidden="true">{items.map((p) => <span key={p.id} className={cx("h-1.5 w-1.5 rounded-full", STATUS_BG[p.status])} />)}</span>
              <span className="tabular ml-auto text-[12px] text-muted">{items.length}</span>
            </div>
            <ul className="divide-y divide-line">{shown.map((p) => <PromiseRow key={p.id} p={p} onOpen={openQuote} />)}</ul>
            {items.length > PER_GROUP && (
              <button onClick={() => setOpen((o) => ({ ...o, [metric]: !all }))}
                className="flex w-full items-center justify-center gap-1 border-t border-line py-2.5 text-[12.5px] font-medium text-accent hover:bg-surface-2">
                {all ? "Show fewer" : `Show all ${items.length}`}
                <Icon name="down" size={14} className={cx("transition-transform", all && "rotate-180")} />
              </button>
            )}
          </section>
        );
      })}
    </div>
  );
}

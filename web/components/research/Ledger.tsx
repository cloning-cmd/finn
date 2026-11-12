"use client";
import type { Claim, PromiseRec, PromiseStatus, Source } from "@/lib/types";
import ClaimList, { type OpenSources } from "./ClaimList";

export const STATUS_LABEL: Record<PromiseStatus, string> = {
  kept: "Kept", on_track: "On track", missed: "Missed", revised_down: "Revised down", quietly_dropped: "Quietly dropped", too_early: "Too early",
};
const STATUS_CLASS: Record<PromiseStatus, string> = {
  kept: "bg-up", on_track: "bg-accent", missed: "bg-down", revised_down: "bg-warn", quietly_dropped: "bg-down", too_early: "bg-muted",
};
const STATUS_TEXT: Record<PromiseStatus, string> = {
  kept: "text-up", on_track: "text-accent", missed: "text-down", revised_down: "text-warn", quietly_dropped: "text-down", too_early: "text-muted",
};
const METRIC_LABEL: Record<string, string> = {
  revenue_growth: "Revenue growth", ebitda_margin: "Operating margin", pat: "Profit", capex: "Capex", net_debt: "Net debt",
  order_book: "Order book", capacity: "Capacity", launch: "Launches", headcount: "Hiring", tax_rate: "Tax rate", payout: "Payout",
  attrition: "Attrition", onsite_mix: "Onsite mix", other: "Other",
};
const METRIC_ORDER = ["revenue_growth", "ebitda_margin", "pat", "capex", "net_debt", "order_book", "capacity", "headcount", "tax_rate", "payout"];
const ORDER: PromiseStatus[] = ["kept", "on_track", "missed", "revised_down", "quietly_dropped", "too_early"];

function Dot({ status, hollow = false }: { status: PromiseStatus; hollow?: boolean }) {
  return <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${hollow ? "border-2 border-line bg-card" : STATUS_CLASS[status]}`} aria-hidden="true" />;
}

/** Promise Ledger: counts by status, then one vertical timeline per promise (said → later mentions → actual). */
export default function Ledger({ ledger, sources, onOpen }: {
  ledger: { summary: Record<PromiseStatus, number>; promises: PromiseRec[]; narrative: Claim[] };
  sources: Source[]; onOpen: OpenSources;
}) {
  const total = ledger.promises.length;
  // One group per metric; hard promises first, newest call first inside a group.
  const groups = Object.entries(ledger.promises.reduce<Record<string, PromiseRec[]>>((acc, p) => { (acc[p.metric] ||= []).push(p); return acc; }, {}))
    .map(([m, items]) => [m, [...items].sort((a, b) => Number(b.hard) - Number(a.hard) || b.said_in.localeCompare(a.said_in))] as [string, PromiseRec[]])
    .sort((a, b) => (METRIC_ORDER.indexOf(a[0]) + 1 || 99) - (METRIC_ORDER.indexOf(b[0]) + 1 || 99) || b[1].length - a[1].length);
  const open = (p: PromiseRec) => {
    const srcs: Source[] = [{ ...p.source, label: `${p.speaker ? p.speaker + " · " : ""}${p.said_in}`, quote: p.quote }];
    if (p.actual_source) srcs.push({ ...p.actual_source, label: `Actual: ${p.actual_source.label}` });
    onOpen(`${p.metric}: ${p.target_text}`, srcs, p.source.id);
  };
  return (
    <section>
      <div className="flex items-baseline gap-2">
        <h2 className="text-[15px] font-semibold">Promise ledger</h2>
        <span className="tabular text-[12px] text-muted">{total} tracked</span>
      </div>
      {total > 0 && (
        <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[12px]">
          {ORDER.filter((s) => ledger.summary[s] > 0).map((s) => (
            <li key={s} className="flex items-center gap-1.5"><Dot status={s} /><span className="tabular">{ledger.summary[s]}</span><span className="text-muted">{STATUS_LABEL[s]}</span></li>
          ))}
        </ul>
      )}
      {total === 0 && <p className="mt-2 text-[12.5px] text-muted">No quantified guidance found in the transcripts on file.</p>}

      {groups.map(([metric, items]) => (
      <div key={metric} className="mt-3">
        <h3 className="mb-1.5 flex items-baseline gap-2 text-[11px] uppercase tracking-wide text-muted">
          <span>{METRIC_LABEL[metric] ?? metric.replace(/_/g, " ")}</span>
          <span className="tabular normal-case">{items.length}</span>
        </h3>
      <ul className="space-y-2">
        {items.map((p) => (
          <li key={p.id}>
            <button onClick={() => open(p)} className="w-full rounded-xl border border-line bg-card px-3 py-2.5 text-left">
              <div className="flex items-baseline gap-2">
                <span className="text-[13.5px] font-medium">{p.metric}</span>
                <span className={`ml-auto text-[11.5px] ${STATUS_TEXT[p.status]}`}>{STATUS_LABEL[p.status]}{!p.hard && " · soft"}</span>
              </div>
              <ol className="mt-2 space-y-1.5 border-l border-line pl-3">
                <li className="relative text-[12.5px]">
                  <span className="absolute -left-[19px] top-1"><Dot status={p.status} hollow /></span>
                  <span className="text-muted">{p.said_in}</span> · {p.target_text}<span className="text-muted"> for {p.period}</span>
                </li>
                {p.later_mentions.map((m, i) => (
                  <li key={i} className="relative text-[12px] text-muted">
                    <span className="absolute -left-[17px] top-1.5 inline-block h-1.5 w-1.5 rounded-full bg-line" aria-hidden="true" />
                    {m.call} · {m.stance === "absent" ? "not mentioned" : m.stance}
                  </li>
                ))}
                <li className="relative text-[12.5px]">
                  <span className="absolute -left-[19px] top-1"><Dot status={p.status} /></span>
                  {p.actual_text ? <>Actual · {p.actual_text}</> : <span className="text-muted">Actual not yet reported</span>}
                </li>
              </ol>
            </button>
          </li>
        ))}
      </ul>
      </div>
      ))}
      {ledger.narrative.length > 0 && <div className="mt-3"><ClaimList claims={ledger.narrative} sources={sources} onOpen={onOpen} /></div>}
    </section>
  );
}

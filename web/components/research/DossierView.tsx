"use client";
import type { ReactNode } from "react";
import type { Dossier } from "@/lib/types";
import { fmtCr } from "@/lib/format";
import Sparkline from "@/components/charts/Sparkline";
import { Badge, Icon, Panel, Stat, TickerAvatar } from "@/components/ui";
import ClaimList, { type OpenSources } from "./ClaimList";
import Ledger from "./Ledger";

export const DOSSIER_TABS = ["overview", "promises", "financials", "sources"] as const;
export type DossierTab = (typeof DOSSIER_TABS)[number];
export const DOSSIER_TAB_LABEL: Record<DossierTab, string> = { overview: "Overview", promises: "Promises", financials: "Financials", sources: "Sources" };

type Fmt = (v: number) => string;
const cr: Fmt = (v) => `₹${fmtCr(v)} Cr`;
const KEY: [string, "ttm" | "ratios", string, Fmt][] = [
  ["revenue", "ttm", "Revenue TTM", cr],
  ["pat", "ttm", "Profit TTM", cr],
  ["opm_pct", "ttm", "Operating margin", (v) => `${v.toFixed(1)}%`],
  ["roce_pct", "ratios", "ROCE", (v) => `${v.toFixed(1)}%`],
  ["pe", "ratios", "P/E", (v) => `${v.toFixed(1)}×`],
  ["mcap_cr", "ratios", "Market cap", cr],
];
const TTM_ROWS: [string, string, Fmt][] = [
  ["revenue", "Revenue", cr], ["ebitda", "EBITDA", cr], ["pat", "PAT", cr], ["opm_pct", "OPM", (v) => `${v.toFixed(1)}%`], ["eps", "EPS", (v) => `₹${v.toFixed(1)}`],
];
const RATIO_ROWS: [string, string, Fmt][] = [
  ["pe", "P/E", (v) => `${v.toFixed(1)}×`], ["roce_pct", "ROCE", (v) => `${v.toFixed(1)}%`], ["roe_pct", "ROE", (v) => `${v.toFixed(1)}%`],
  ["div_yield_pct", "Dividend yield", (v) => `${v.toFixed(2)}%`], ["mcap_cr", "Market cap", cr], ["pat_margin_pct", "PAT margin", (v) => `${v.toFixed(1)}%`],
];
const ok = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function Grid({ rows, data }: { rows: [string, string, Fmt][]; data: Record<string, number> }) {
  const present = rows.filter(([k]) => ok(data[k]));
  if (!present.length) return <p className="text-[13px] text-muted">Not available.</p>;
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
      {present.map(([k, label, f]) => <Stat key={k} label={label} value={f(data[k])} />)}
    </dl>
  );
}

function TrendRow({ label, years, values, fmt, upIsGood = true }: { label: string; years: string[]; values: number[]; fmt: Fmt; upIsGood?: boolean }) {
  if (!values?.length) return null;
  const first = values[0], last = values[values.length - 1];
  const up = last >= first;
  return (
    <li className="flex items-center gap-3 py-3">
      <div className="w-28 shrink-0">
        <div className="text-[13px] font-medium">{label}</div>
        <div className="tabular text-[11.5px] text-muted">{years[0]} – {years[years.length - 1]}</div>
      </div>
      <Sparkline values={values} positive={upIsGood ? up : !up} className="h-9 min-w-0 flex-1" />
      <div className="tabular w-28 shrink-0 text-right">
        <div className="text-[13.5px] font-semibold">{fmt(last)}</div>
        <div className="text-[11.5px] text-muted">from {fmt(first)}</div>
      </div>
    </li>
  );
}

function Trend({ title, children, notes }: { title: string; children: ReactNode; notes?: ReactNode }) {
  return (
    <Panel title={title}>
      <ul className="-my-3 divide-y divide-line">{children}</ul>
      {notes && <div className="mt-4 border-t border-line pt-4">{notes}</div>}
    </Panel>
  );
}

/** Company header shown above the tabs. */
export function DossierHeader({ d, action }: { d: Dossier; action?: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <TickerAvatar ticker={d.ticker} size={48} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h1 className="truncate text-[22px] font-semibold leading-tight tracking-[-0.02em]">{d.ticker}</h1>
          <Badge>{d.basis}</Badge>
        </div>
        <div className="truncate text-[13px] text-muted">{d.name}</div>
      </div>
      {action}
    </div>
  );
}

/** One tab of the dossier. */
export default function DossierView({ d, tab, onOpen }: { d: Dossier; tab: DossierTab; onOpen: OpenSources }) {
  const yrs = d.trajectory.years;
  const keyStats = KEY.filter(([k, from]) => ok(d.financials[from][k]));

  if (tab === "promises") return <Ledger ledger={d.ledger} sources={d.sources} onOpen={onOpen} />;

  if (tab === "financials") {
    return (
      <div className="space-y-4">
        <Panel title="Trailing twelve months"><Grid rows={TTM_ROWS} data={d.financials.ttm} /></Panel>
        <Panel title="Ratios"><Grid rows={RATIO_ROWS} data={d.financials.ratios} /></Panel>
        <Trend title="Trajectory" notes={d.trajectory.notes.length ? <ClaimList claims={d.trajectory.notes} sources={d.sources} onOpen={onOpen} dense /> : null}>
          <TrendRow label="Revenue" years={yrs} values={d.trajectory.series.revenue} fmt={cr} />
          <TrendRow label="EBITDA" years={yrs} values={d.trajectory.series.ebitda} fmt={cr} />
          <TrendRow label="PAT" years={yrs} values={d.trajectory.series.pat} fmt={cr} />
          <TrendRow label="OPM" years={yrs} values={d.trajectory.series.opm_pct} fmt={(v) => `${v.toFixed(0)}%`} />
        </Trend>
        <Trend title="Balance sheet" notes={d.balance_sheet.notes.length ? <ClaimList claims={d.balance_sheet.notes} sources={d.sources} onOpen={onOpen} dense /> : null}>
          <TrendRow label="Debt / equity" years={yrs} values={d.balance_sheet.de} fmt={(v) => v.toFixed(2)} upIsGood={false} />
          <TrendRow label="Net debt" years={yrs} values={d.balance_sheet.net_debt} fmt={cr} upIsGood={false} />
          <TrendRow label="Working capital days" years={yrs} values={d.balance_sheet.wc_days} fmt={(v) => v.toFixed(0)} upIsGood={false} />
        </Trend>
        <Trend title="Cash quality" notes={(d.cash_quality.flag || d.cash_quality.notes.length) ? (
          <>
            {d.cash_quality.flag && <p className="mb-3 text-[13px] text-warn">{d.cash_quality.flag}</p>}
            <ClaimList claims={d.cash_quality.notes} sources={d.sources} onOpen={onOpen} dense />
          </>
        ) : null}>
          <TrendRow label="CFO / PAT" years={yrs} values={d.cash_quality.cfo_pat} fmt={(v) => v.toFixed(2)} />
          <TrendRow label="Free cash flow" years={yrs} values={d.cash_quality.fcf} fmt={cr} />
        </Trend>
      </div>
    );
  }

  if (tab === "sources") {
    return (
      <div className="space-y-4">
        <Panel title="Documents read" pad={false}>
          <ul className="divide-y divide-line">
            {d.sources.map((s) => (
              <li key={s.id}>
                <a href={s.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-2">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-muted"><Icon name="doc" size={16} /></span>
                  <span className="min-w-0 flex-1 truncate text-[13.5px]">{s.label}</span>
                  <Icon name="chevron" size={16} className="text-faint" />
                </a>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Cost of this dossier">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
            <Stat label="Model spend" value={`₹${d.cost.inr.toFixed(2)}`} />
            <Stat label="Tokens" value={`${Math.round((d.cost.tokens_in + d.cost.tokens_out) / 1000)}k`} />
            <Stat label="From cache" value={`${Math.round(d.cost.cache_hit_pct)}%`} />
            <Stat label="Built" value={new Date(d.as_of).toLocaleDateString("en-IN", { day: "numeric", month: "short" })} />
          </dl>
          {d.cost.models.length > 0 && <p className="mt-3 text-[12px] text-muted">{d.cost.models.map((m) => m.replace(/^[a-z]+\//, "")).join(" · ")}</p>}
        </Panel>
        {d.gaps.length > 0 && (
          <Panel title="Not covered">
            <ul className="space-y-1.5 text-[13px] text-muted">{d.gaps.map((g, i) => <li key={i} className="flex gap-2.5"><span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-faint" />{g}</li>)}</ul>
          </Panel>
        )}
      </div>
    );
  }

  // overview
  return (
    <div className="space-y-4">
      <Panel title="Verdict" action={<span className="tabular">₹{d.cost.inr.toFixed(2)} · {Math.round(d.cost.cache_hit_pct)}% cached</span>}>
        <ClaimList claims={d.verdict} sources={d.sources} onOpen={onOpen} empty="Verdict needs a strong-model pass. Numbers are from filings and screener tables." />
      </Panel>

      {keyStats.length > 0 && (
        <Panel title="Key numbers">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3.5 sm:grid-cols-3">
            {keyStats.map(([k, from, label, f]) => <Stat key={k} label={label} value={f(d.financials[from][k])} />)}
          </dl>
        </Panel>
      )}

      {d.snapshot && (d.snapshot.what.length > 0 || d.snapshot.segments.length > 0) && (
        <Panel title="What the company does">
          <ClaimList claims={d.snapshot.what} sources={d.sources} onOpen={onOpen} dense />
          {d.snapshot.segments.length > 0 && (
            <div className="mt-4">
              <div className="flex h-2 gap-0.5 overflow-hidden rounded-full">
                {d.snapshot.segments.map((s, i) => <div key={s.name} style={{ flexGrow: s.share_pct, background: `hsl(${222 + i * 38} 70% ${60 - i * 4}%)` }} />)}
              </div>
              <ul className="mt-2.5 space-y-1.5">
                {d.snapshot.segments.map((s, i) => (
                  <li key={s.name} className="flex items-center gap-2 text-[12.5px]">
                    <span className="h-2 w-2 rounded-full" style={{ background: `hsl(${222 + i * 38} 70% ${60 - i * 4}%)` }} />
                    <span className="truncate">{s.name}</span>
                    <span className="tabular ml-auto text-muted">{s.share_pct}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>
      )}

      {(d.bull.length > 0 || d.bear.length > 0) && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Panel title={<span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-up" />Bull case</span>}>
            <ClaimList claims={d.bull} sources={d.sources} onOpen={onOpen} dense empty="None verified." />
          </Panel>
          <Panel title={<span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-down" />Bear case</span>}>
            <ClaimList claims={d.bear} sources={d.sources} onOpen={onOpen} dense empty="None verified." />
          </Panel>
        </div>
      )}
    </div>
  );
}

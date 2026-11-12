"use client";
import type { Dossier } from "@/lib/types";
import { fmtCr } from "@/lib/format";
import Sparkline from "@/components/charts/Sparkline";
import ClaimList, { type OpenSources } from "./ClaimList";
import Ledger from "./Ledger";

const TTM_ROWS: [string, string, (v: number) => string][] = [
  ["revenue", "Revenue TTM", (v) => `₹${fmtCr(v)} Cr`],
  ["ebitda", "EBITDA TTM", (v) => `₹${fmtCr(v)} Cr`],
  ["pat", "PAT TTM", (v) => `₹${fmtCr(v)} Cr`],
  ["opm_pct", "OPM", (v) => `${v.toFixed(1)}%`],
  ["eps", "EPS TTM", (v) => `₹${v.toFixed(1)}`],
];
const RATIO_ROWS: [string, string, (v: number) => string][] = [
  ["pe", "P/E", (v) => `${v.toFixed(1)}×`],
  ["roce_pct", "ROCE", (v) => `${v.toFixed(1)}%`],
  ["roe_pct", "ROE", (v) => `${v.toFixed(1)}%`],
  ["div_yield_pct", "Div. yield", (v) => `${v.toFixed(2)}%`],
  ["mcap_cr", "Market cap", (v) => `₹${fmtCr(v)} Cr`],
  ["pat_margin_pct", "PAT margin", (v) => `${v.toFixed(1)}%`],
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6">
      <h2 className="text-[15px] font-semibold">{title}</h2>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function Grid({ rows, data }: { rows: [string, string, (v: number) => string][]; data: Record<string, number> }) {
  const present = rows.filter(([k]) => typeof data[k] === "number" && Number.isFinite(data[k]));
  if (!present.length) return <p className="text-[12.5px] text-muted">Not available.</p>;
  return (
    <dl className="grid grid-cols-3 gap-x-3 gap-y-2">
      {present.map(([k, label, f]) => (
        <div key={k}>
          <dt className="text-[11px] text-muted">{label}</dt>
          <dd className="tabular text-[13.5px]">{f(data[k])}</dd>
        </div>
      ))}
    </dl>
  );
}

function TrendRow({ label, years, values, fmt, upIsGood = true }: { label: string; years: string[]; values: number[]; fmt: (v: number) => string; upIsGood?: boolean }) {
  if (!values?.length) return null;
  const first = values[0], last = values[values.length - 1];
  const up = last >= first;
  return (
    <li className="flex items-center gap-3 py-1.5">
      <div className="w-24 shrink-0">
        <div className="text-[12.5px]">{label}</div>
        <div className="tabular text-[11px] text-muted">{years[0]} → {years[years.length - 1]}</div>
      </div>
      <Sparkline values={values} positive={upIsGood ? up : !up} className="h-7 flex-1" />
      <div className="tabular w-24 shrink-0 text-right text-[12.5px]">
        <div>{fmt(last)}</div>
        <div className="text-[11px] text-muted">from {fmt(first)}</div>
      </div>
    </li>
  );
}

/** The full dossier: verdict + receipt, ledger (hero), then the numeric sections and bull/bear. */
export default function DossierView({ d, onOpen }: { d: Dossier; onOpen: OpenSources }) {
  const yrs = d.trajectory.years;
  const cr = (v: number) => `₹${fmtCr(v)} Cr`;
  return (
    <div>
      <header className="mt-3">
        <div className="flex items-baseline gap-2">
          <h1 className="text-[20px] font-semibold tracking-tight">{d.ticker}</h1>
          <span className="truncate text-[13px] text-muted">{d.name}</span>
        </div>
        <p className="tabular mt-0.5 text-[11.5px] text-muted">
          {d.basis} · as of {new Date(d.as_of).toLocaleDateString("en-IN", { day: "numeric", month: "short" })} ·
          ₹{d.cost.inr.toFixed(2)} · {Math.round((d.cost.tokens_in + d.cost.tokens_out) / 1000)}k tokens · {Math.round(d.cost.cache_hit_pct)}% cached · {d.cost.models.length} model{d.cost.models.length === 1 ? "" : "s"}
        </p>
        <div className="mt-3">
          <ClaimList claims={d.verdict} sources={d.sources} onOpen={onOpen} empty="Verdict needs a strong-model pass. Numbers below are from filings and screener tables." />
        </div>
      </header>

      <div className="mt-6"><Ledger ledger={d.ledger} sources={d.sources} onOpen={onOpen} /></div>

      {d.snapshot && (d.snapshot.what.length > 0 || d.snapshot.segments.length > 0) && (
        <Section title="Snapshot">
          <ClaimList claims={d.snapshot.what} sources={d.sources} onOpen={onOpen} />
          {d.snapshot.segments.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5 text-[11.5px]">
              {d.snapshot.segments.map((s) => <li key={s.name} className="rounded-full border border-line px-2 py-0.5"><span>{s.name}</span><span className="tabular text-muted"> {s.share_pct}%</span></li>)}
            </ul>
          )}
        </Section>
      )}

      <Section title="Financials">
        <Grid rows={TTM_ROWS} data={d.financials.ttm} />
        <div className="mt-3 border-t border-line pt-3"><Grid rows={RATIO_ROWS} data={d.financials.ratios} /></div>
      </Section>

      <Section title="Trajectory">
        <ul className="divide-y divide-line">
          <TrendRow label="Revenue" years={yrs} values={d.trajectory.series.revenue} fmt={cr} />
          <TrendRow label="EBITDA" years={yrs} values={d.trajectory.series.ebitda} fmt={cr} />
          <TrendRow label="PAT" years={yrs} values={d.trajectory.series.pat} fmt={cr} />
          <TrendRow label="OPM" years={yrs} values={d.trajectory.series.opm_pct} fmt={(v) => `${v.toFixed(0)}%`} />
        </ul>
        <div className="mt-2"><ClaimList claims={d.trajectory.notes} sources={d.sources} onOpen={onOpen} /></div>
      </Section>

      <Section title="Balance sheet">
        <ul className="divide-y divide-line">
          <TrendRow label="Debt/equity" years={yrs} values={d.balance_sheet.de} fmt={(v) => v.toFixed(2)} upIsGood={false} />
          <TrendRow label="Net debt" years={yrs} values={d.balance_sheet.net_debt} fmt={cr} upIsGood={false} />
          <TrendRow label="WC days" years={yrs} values={d.balance_sheet.wc_days} fmt={(v) => v.toFixed(0)} upIsGood={false} />
        </ul>
        <div className="mt-2"><ClaimList claims={d.balance_sheet.notes} sources={d.sources} onOpen={onOpen} /></div>
      </Section>

      <Section title="Cash quality">
        {d.cash_quality.flag && <p className="mb-2 text-[12.5px] text-warn">{d.cash_quality.flag}</p>}
        <ul className="divide-y divide-line">
          <TrendRow label="CFO / PAT" years={yrs} values={d.cash_quality.cfo_pat} fmt={(v) => v.toFixed(2)} />
          <TrendRow label="Free cash flow" years={yrs} values={d.cash_quality.fcf} fmt={cr} />
        </ul>
        <div className="mt-2"><ClaimList claims={d.cash_quality.notes} sources={d.sources} onOpen={onOpen} /></div>
      </Section>

      {(d.bull.length > 0 || d.bear.length > 0) && (
        <Section title="Bull / Bear">
          <div className="grid grid-cols-1 gap-3">
            <div className="rounded-xl border border-line p-3"><h3 className="mb-1.5 text-[11px] uppercase tracking-wide text-up">Bull</h3><ClaimList claims={d.bull} sources={d.sources} onOpen={onOpen} /></div>
            <div className="rounded-xl border border-line p-3"><h3 className="mb-1.5 text-[11px] uppercase tracking-wide text-down">Bear</h3><ClaimList claims={d.bear} sources={d.sources} onOpen={onOpen} /></div>
          </div>
        </Section>
      )}

      <Section title="Sources">
        <ul className="space-y-1">
          {d.sources.map((s) => (
            <li key={s.id}><a href={s.url} target="_blank" rel="noopener noreferrer" className="text-[12.5px] text-muted underline-offset-2 hover:underline">{s.label}</a></li>
          ))}
        </ul>
      </Section>

      {d.gaps.length > 0 && (
        <section className="mt-6 rounded-xl border border-dashed border-line p-3">
          <h2 className="text-[11px] uppercase tracking-wide text-muted">Not covered</h2>
          <ul className="mt-1 space-y-0.5 text-[12px] text-muted">{d.gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
        </section>
      )}
    </div>
  );
}

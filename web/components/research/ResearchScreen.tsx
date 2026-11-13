"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Dossier, ProgressEvent, Source } from "@/lib/types";
import { api, researchStream, type QAResponse } from "@/lib/api";
import SourceSheet, { type SheetTarget } from "@/components/SourceSheet";
import { Button, Empty, Icon, PageHeader, Segmented, SectionLabel, Skeleton, Spinner, TickerAvatar, cx } from "@/components/ui";
import DossierView, { DOSSIER_TABS, DOSSIER_TAB_LABEL, DossierHeader, type DossierTab } from "./DossierView";
import ClaimList from "./ClaimList";

const SUGGESTED: [string, string][] = [
  ["INFY", "Infosys"], ["BAJFINANCE", "Bajaj Finance"], ["POLYCAB", "Polycab India"], ["PIDILITIND", "Pidilite Industries"], ["TATAPOWER", "Tata Power"],
];
const RECENT_KEY = "finn.research.recent";

function readRecent(): string[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]") as string[]; } catch { return []; }
}
function pushRecent(t: string) {
  try { localStorage.setItem(RECENT_KEY, JSON.stringify([t, ...readRecent().filter((x) => x !== t)].slice(0, 6))); } catch { /* private mode */ }
}

// The build's progress events, folded into five user-facing stages.
const STAGES = [
  { label: "Find the company", steps: ["resolve"] },
  { label: "Financial tables", steps: ["tables", "screener"] },
  { label: "Annual report and call transcripts", steps: ["documents", "annual_report", "transcript", "chunks"] },
  { label: "Track management guidance", steps: ["guidance", "ledger"] },
  { label: "Write and check citations", steps: ["synthesis", "verify", "cache"] },
];
const stageOf = (step: string) => STAGES.findIndex((s) => s.steps.includes(step));

function BuildProgress({ ticker, log }: { ticker: string; log: ProgressEvent[] }) {
  const finished = log.some((e) => e.step === "done");
  const reached = Math.max(0, ...log.map((e) => stageOf(e.step)));
  const doneStage = (i: number) => finished || i < reached || log.some((e) => stageOf(e.step) === i && e.status === "done" && (i !== 2 || e.step === "documents"));
  const doneCount = STAGES.filter((_, i) => doneStage(i)).length;
  const pct = finished ? 100 : Math.min(95, Math.round(((doneCount + 0.4) / STAGES.length) * 100));
  const detailFor = (i: number) => [...log].reverse().find((e) => stageOf(e.step) === i && e.detail)?.detail;
  const [showLog, setShowLog] = useState(false);
  return (
    <section className="surface mt-2 rounded-2xl p-4">
      <div className="flex items-center gap-3">
        <TickerAvatar ticker={ticker} size={40} />
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-semibold">Building {ticker}</div>
          <div className="text-[12.5px] text-muted">First build takes a minute or two. Later opens are instant.</div>
        </div>
        <span className="tabular text-[13px] font-medium text-muted">{pct}%</span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-2">
        <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </div>
      <ol className="mt-4 space-y-3">
        {STAGES.map((s, i) => {
          const done = doneStage(i);
          const active = !done && i === reached;
          return (
            <li key={s.label} className="flex items-start gap-3">
              <span className={cx("mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
                done ? "bg-up/15 text-up" : active ? "" : "border border-line")}>
                {done ? <Icon name="check" size={13} strokeWidth={2.6} /> : active ? <Spinner size={16} /> : null}
              </span>
              <div className="min-w-0">
                <div className={cx("text-[13.5px]", done || active ? "text-fg" : "text-faint")}>{s.label}</div>
                {(done || active) && detailFor(i) && <div className="truncate text-[12px] text-muted">{detailFor(i)}</div>}
              </div>
            </li>
          );
        })}
      </ol>
      <button onClick={() => setShowLog((v) => !v)} className="mt-4 text-[12px] font-medium text-muted hover:text-fg">{showLog ? "Hide" : "Show"} build log</button>
      {showLog && (
        <ol className="tabular mt-2 max-h-56 space-y-0.5 overflow-y-auto rounded-xl bg-surface-2 p-3 font-mono text-[11px] text-muted">
          {log.map((e, i) => (
            <li key={i} className="flex gap-2">
              <span className={cx("w-9 shrink-0", e.status === "error" ? "text-down" : e.status === "done" ? "text-up" : e.status === "skip" ? "text-warn" : "")}>{e.status}</span>
              <span className="text-fg">{e.step}</span>
              {e.detail && <span className="truncate">{e.detail}</span>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

type Phase = "idle" | "loading" | "building" | "ready" | "error";
interface QAItem { q: string; a?: QAResponse; err?: string }

export default function ResearchScreen() {
  const params = useSearchParams();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [ticker, setTicker] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [log, setLog] = useState<ProgressEvent[]>([]);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const [sheet, setSheet] = useState<{ target: SheetTarget; focus?: string } | null>(null);
  const [qa, setQa] = useState<QAItem[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [tab, setTab] = useState<DossierTab>("overview");
  const seeded = useRef(false);

  useEffect(() => { setRecent(readRecent()); }, []);

  const load = useCallback(async (t: string, force = false) => {
    const sym = t.trim().toUpperCase();
    if (!sym) return;
    setTicker(sym); setDossier(null); setErr(null); setLog([]); setQa([]); setTab("overview");
    pushRecent(sym); setRecent(readRecent());
    router.replace(`/research?t=${encodeURIComponent(sym)}`);
    if (!force) {
      setPhase("loading");
      try { setDossier(await api.research(sym)); setPhase("ready"); return; } catch { /* not cached: build */ }
    }
    setPhase("building");
    try {
      const d = await researchStream(sym, (e) => setLog((l) => [...l, e]), force);
      setDossier(d); setPhase("ready");
    } catch (e) { setErr(String(e instanceof Error ? e.message : e)); setPhase("error"); }
  }, [router]);

  // Deep links from Brief chips: /research?t=INFY&q=…
  useEffect(() => {
    if (seeded.current) return;
    const t = params.get("t");
    if (t) { seeded.current = true; setQuery(t.toUpperCase()); void load(t); }
    const q = params.get("q");
    if (q) setQuestion(q);
  }, [params, load]);

  const openSources = useCallback((headline: string, sources: Source[], focus?: string) => {
    setSheet({ target: { ticker: ticker ?? "", headline, sources }, focus });
  }, [ticker]);

  const ask = useCallback(async () => {
    const q = question.trim();
    if (!q || !ticker || asking) return;
    setAsking(true); setQuestion("");
    setQa((l) => [...l, { q }]);
    try {
      const a = await api.qa(ticker, q);
      setQa((l) => l.map((it) => (it.q === q && !it.a && !it.err ? { ...it, a } : it)));
    } catch (e) {
      setQa((l) => l.map((it) => (it.q === q && !it.a && !it.err ? { ...it, err: String(e instanceof Error ? e.message : e) } : it)));
    } finally { setAsking(false); }
  }, [question, ticker, asking]);

  const reset = () => { setPhase("idle"); setTicker(null); setDossier(null); setQuery(""); router.replace("/research"); };

  return (
    <main className={phase === "ready" ? "pb-24" : undefined}>
      <PageHeader title="Research" eyebrow="Any NSE company">
        <form onSubmit={(e) => { e.preventDefault(); void load(query); }} className="flex items-center gap-2">
          <label className="flex h-11 flex-1 items-center gap-2 rounded-xl bg-surface-2 px-3 focus-within:ring-2 focus-within:ring-accent/50">
            <Icon name="search" size={17} className="text-muted" />
            <input value={query} onChange={(e) => setQuery(e.target.value.toUpperCase())} placeholder="Search a ticker, e.g. TATAPOWER"
              autoCapitalize="characters" autoCorrect="off" spellCheck={false} inputMode="text" aria-label="NSE ticker"
              className="min-w-0 flex-1 bg-transparent text-[14px] outline-none placeholder:text-faint" />
            {query && <button type="button" onClick={() => setQuery("")} aria-label="Clear" className="text-faint hover:text-fg"><Icon name="x" size={15} /></button>}
          </label>
          <Button type="submit" disabled={!query.trim() || phase === "building"} className="h-11">Open</Button>
        </form>
      </PageHeader>

      {phase === "idle" && (
        <>
          {recent.length > 0 && (
            <>
              <SectionLabel>Recent</SectionLabel>
              <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
                {recent.map((t) => (
                  <button key={t} onClick={() => { setQuery(t); void load(t); }} className="surface flex shrink-0 items-center gap-2 rounded-xl py-2 pl-2 pr-3 transition-colors hover:bg-surface-2">
                    <TickerAvatar ticker={t} size={26} /><span className="text-[13px] font-medium">{t}</span>
                  </button>
                ))}
              </div>
            </>
          )}
          <SectionLabel>Suggested</SectionLabel>
          <ul className="surface divide-y divide-line overflow-hidden rounded-2xl">
            {SUGGESTED.map(([t, name]) => (
              <li key={t}>
                <button onClick={() => { setQuery(t); void load(t); }} className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2">
                  <TickerAvatar ticker={t} size={36} />
                  <div className="min-w-0 flex-1"><div className="text-[14px] font-medium">{t}</div><div className="truncate text-[12px] text-muted">{name}</div></div>
                  <Icon name="chevron" size={16} className="text-faint" />
                </button>
              </li>
            ))}
          </ul>
          <SectionLabel>How it works</SectionLabel>
          <ul className="surface space-y-3 rounded-2xl p-4 text-[13px]">
            {[
              ["doc", "Reads the latest annual report and the last five concall transcripts, plus screener tables."],
              ["check", "Every number is computed in code; every sentence carries a source and is checked against it."],
              ["clock", "Tracks what management promised and whether it happened."],
            ].map(([icon, text]) => (
              <li key={text} className="flex gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent/12 text-accent"><Icon name={icon as "doc"} size={15} /></span>
                <span className="pt-1 text-muted">{text}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {phase === "loading" && <div className="mt-2 space-y-3"><Skeleton className="h-14" /><Skeleton className="h-10" /><Skeleton className="h-40" /><Skeleton className="h-28" /></div>}

      {phase === "building" && ticker && <BuildProgress ticker={ticker} log={log} />}

      {phase === "error" && (
        <Empty icon={<Icon name="x" />} title={`Could not build ${ticker}`} body={err ?? undefined}
          action={<div className="flex gap-2"><Button size="sm" onClick={() => ticker && load(ticker, true)}>Retry</Button><Button size="sm" variant="secondary" onClick={reset}>Another ticker</Button></div>} />
      )}

      {phase === "ready" && dossier && (
        <>
          <div className="mt-1">
            <DossierHeader d={dossier} action={
              <button onClick={() => ticker && load(ticker, true)} title="Rebuild from the latest documents" aria-label="Rebuild"
                className="flex h-9 w-9 items-center justify-center rounded-xl text-muted transition-colors hover:bg-surface-2 hover:text-fg"><Icon name="refresh" size={17} /></button>
            } />
          </div>
          <div className="sticky z-20 -mx-4 mt-4 bg-bg/85 px-4 pb-3 pt-1 backdrop-blur-xl md:-mx-6 md:px-6" style={{ top: "calc(env(safe-area-inset-top, 0px) + 132px)" }}>
            <Segmented options={DOSSIER_TABS} value={tab} onChange={setTab} labels={DOSSIER_TAB_LABEL} />
          </div>
          <DossierView d={dossier} tab={tab} onOpen={openSources} />

          {qa.length > 0 && (
            <>
              <SectionLabel>Your questions</SectionLabel>
              <div className="space-y-3">
                {qa.map((it, i) => (
                  <div key={i} className="surface rounded-2xl p-4">
                    <div className="flex justify-end"><p className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-3 py-2 text-[13.5px] text-accent-fg">{it.q}</p></div>
                    <div className="mt-3">
                      {!it.a && !it.err && <p className="flex items-center gap-2 text-[13px] text-muted"><Spinner size={14} />Reading the transcripts</p>}
                      {it.err && <p className="text-[13px] text-down">{it.err}</p>}
                      {it.a && (
                        <>
                          <ClaimList claims={it.a.claims} sources={[...dossier.sources, ...it.a.sources]} onOpen={openSources} empty="Not disclosed in the documents on file." dense />
                          {it.a.gaps.length > 0 && <p className="mt-2 text-[12px] text-muted">{it.a.gaps.join(" · ")}</p>}
                          <p className="tabular mt-2 text-[11px] text-faint">{it.a.model?.replace(/^[a-z]+\//, "") ?? "no model"} · ₹{it.a.cost.toFixed(2)}</p>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}

      {ticker && phase === "ready" && (
        <form onSubmit={(e) => { e.preventDefault(); void ask(); }}
          className="fixed inset-x-0 z-30 mx-auto max-w-[464px] px-3 md:max-w-[624px]"
          style={{ bottom: "calc(env(safe-area-inset-bottom, 0px) + 82px)" }}>
          <div className="flex items-center gap-2 rounded-2xl border border-line bg-surface/95 p-1.5 pl-4 shadow-[0_8px_30px_rgb(0_0_0/0.25)] backdrop-blur-xl">
            <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={`Ask about ${ticker}`} aria-label={`Ask about ${ticker}`}
              className="min-w-0 flex-1 bg-transparent text-[14px] outline-none placeholder:text-faint" />
            <button type="submit" disabled={!question.trim() || asking} aria-label="Ask"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-fg transition disabled:opacity-30">
              {asking ? <Spinner size={14} /> : <Icon name="arrowUp" size={17} strokeWidth={2.2} />}
            </button>
          </div>
        </form>
      )}

      <SourceSheet card={sheet?.target ?? null} focus={sheet?.focus} onClose={() => setSheet(null)} />
    </main>
  );
}

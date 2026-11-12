"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Dossier, ProgressEvent, Source } from "@/lib/types";
import { api, researchStream, type QAResponse } from "@/lib/api";
import SourceSheet, { type SheetTarget } from "@/components/SourceSheet";
import DossierView from "./DossierView";
import ClaimList from "./ClaimList";

const SUGGESTED = ["INFY", "BAJFINANCE", "POLYCAB", "PIDILITIND", "TATAPOWER"];
const RECENT_KEY = "finn.research.recent";

function readRecent(): string[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]") as string[]; } catch { return []; }
}
function pushRecent(t: string) {
  try { localStorage.setItem(RECENT_KEY, JSON.stringify([t, ...readRecent().filter((x) => x !== t)].slice(0, 6))); } catch { /* private mode */ }
}

const STEP_LABEL: Record<string, string> = {
  resolve: "Resolve ticker", screener: "Screener tables", documents: "Documents", annual_report: "Annual report", transcript: "Transcript",
  tables: "Financial tables", chunks: "Chunks + embeddings", guidance: "Guidance extraction", ledger: "Promise matching", synthesis: "Synthesis", done: "Done",
  verify: "Citation check", cache: "Cache",
};

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
  const seeded = useRef(false);

  useEffect(() => { setRecent(readRecent()); }, []);

  const load = useCallback(async (t: string, force = false) => {
    const sym = t.trim().toUpperCase();
    if (!sym) return;
    setTicker(sym); setDossier(null); setErr(null); setLog([]); setQa([]);
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

  const lastStep = log.length ? log[log.length - 1] : null;

  return (
    <main className="pb-24">
      <header className="sticky top-0 z-30 -mx-4 border-b border-line bg-bg/95 px-4 pb-2 pt-3 backdrop-blur" style={{ top: "env(safe-area-inset-top, 0px)" }}>
        <form onSubmit={(e) => { e.preventDefault(); void load(query); }} className="flex items-center gap-2">
          <h1 className="text-[17px] font-semibold tracking-tight">Research</h1>
          <input
            value={query} onChange={(e) => setQuery(e.target.value.toUpperCase())} placeholder="NSE ticker"
            autoCapitalize="characters" autoCorrect="off" spellCheck={false} inputMode="text"
            className="ml-auto w-36 rounded-full border border-line bg-card px-3 py-1 text-[13px] outline-none focus:border-accent"
          />
          <button type="submit" disabled={!query.trim() || phase === "building"} className="rounded-full bg-fg px-3 py-1 text-[12px] text-bg disabled:opacity-40">Go</button>
        </form>
      </header>

      {phase === "idle" && (
        <section className="mt-5 space-y-5">
          {recent.length > 0 && (
            <div>
              <h2 className="text-[11px] uppercase tracking-wide text-muted">Recent</h2>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">{recent.map((t) => <li key={t}><button onClick={() => { setQuery(t); void load(t); }} className="rounded-full border border-line px-2.5 py-1 text-[12.5px]">{t}</button></li>)}</ul>
            </div>
          )}
          <div>
            <h2 className="text-[11px] uppercase tracking-wide text-muted">Suggested</h2>
            <ul className="mt-1.5 flex flex-wrap gap-1.5">{SUGGESTED.map((t) => <li key={t}><button onClick={() => { setQuery(t); void load(t); }} className="rounded-full border border-line px-2.5 py-1 text-[12.5px]">{t}</button></li>)}</ul>
          </div>
          <p className="text-[12.5px] text-muted">Any NSE symbol. Sources: annual reports, concall transcripts, screener tables. First build takes a minute; later opens are cached.</p>
        </section>
      )}

      {phase === "loading" && <div className="mt-3 space-y-2">{[0, 1, 2].map((i) => <div key={i} className="h-20 animate-pulse rounded-xl border border-line bg-card" />)}</div>}

      {phase === "building" && (
        <section className="mt-4">
          <p className="text-[13.5px]">Building {ticker}. {lastStep ? `${STEP_LABEL[lastStep.step] ?? lastStep.step}${lastStep.detail ? ` · ${lastStep.detail}` : ""}` : "Starting"}</p>
          <ol className="tabular mt-3 space-y-1 font-mono text-[11.5px] text-muted">
            {log.map((e, i) => (
              <li key={i} className="flex gap-2">
                <span className={`w-10 shrink-0 ${e.status === "error" ? "text-down" : e.status === "done" ? "text-up" : e.status === "skip" ? "text-warn" : ""}`}>{e.status}</span>
                <span className="text-fg">{STEP_LABEL[e.step] ?? e.step}</span>
                {e.detail && <span className="truncate">{e.detail}</span>}
              </li>
            ))}
          </ol>
        </section>
      )}

      {phase === "error" && (
        <section className="mt-6">
          <p className="text-[13.5px]">Could not build a dossier for {ticker}.</p>
          <p className="mt-1 text-[12.5px] text-muted">{err}</p>
          <button onClick={() => setPhase("idle")} className="mt-3 rounded-full border border-line px-3 py-1 text-[12.5px]">Try another ticker</button>
        </section>
      )}

      {phase === "ready" && dossier && (
        <>
          <DossierView d={dossier} onOpen={openSources} />
          <div className="mt-4 flex gap-2">
            <button onClick={() => ticker && load(ticker, true)} className="rounded-full border border-line px-3 py-1 text-[12px] text-muted">Rebuild</button>
          </div>

          {qa.length > 0 && (
            <section className="mt-6 space-y-3">
              <h2 className="text-[15px] font-semibold">Asked</h2>
              {qa.map((it, i) => (
                <div key={i} className="rounded-xl border border-line bg-card px-3 py-2.5">
                  <p className="text-[13px] font-medium">{it.q}</p>
                  <div className="mt-1.5">
                    {!it.a && !it.err && <p className="text-[12.5px] text-muted">Looking through the transcripts…</p>}
                    {it.err && <p className="text-[12.5px] text-muted">{it.err}</p>}
                    {it.a && (
                      <>
                        <ClaimList claims={it.a.claims} sources={[...dossier.sources, ...it.a.sources]} onOpen={openSources} empty="Not disclosed in the documents on file." />
                        {it.a.gaps.length > 0 && <p className="mt-1.5 text-[11.5px] text-muted">{it.a.gaps.join(" · ")}</p>}
                        <p className="tabular mt-1.5 text-[11px] text-muted">{it.a.model ?? "no model"} · ₹{it.a.cost.toFixed(2)}</p>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </section>
          )}
        </>
      )}

      {ticker && phase === "ready" && (
        <form onSubmit={(e) => { e.preventDefault(); void ask(); }}
              className="fixed inset-x-0 z-30 mx-auto max-w-md border-t border-line bg-bg/95 px-4 py-2 backdrop-blur"
              style={{ bottom: "calc(env(safe-area-inset-bottom, 0px) + 3.5rem)" }}>
          <div className="flex items-center gap-2">
            <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={`Ask about ${ticker} (answers quote the filings)`}
                   className="flex-1 rounded-full border border-line bg-card px-3 py-1.5 text-[13px] outline-none focus:border-accent" />
            <button type="submit" disabled={!question.trim() || asking} className="rounded-full bg-fg px-3 py-1.5 text-[12px] text-bg disabled:opacity-40">Ask</button>
          </div>
        </form>
      )}

      <SourceSheet card={sheet?.target ?? null} focus={sheet?.focus} onClose={() => setSheet(null)} />
    </main>
  );
}

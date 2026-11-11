"use client";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Brief } from "@/lib/types";
import { CATEGORY_LABEL } from "@/lib/types";
import { api } from "@/lib/api";
import CardView from "@/components/cards/CardView";

const WINDOWS = ["24h", "3d", "7d"] as const;

export default function BriefScreen() {
  const params = useSearchParams();
  const fixture = params.get("fixture") === "1" || process.env.NEXT_PUBLIC_FIXTURE === "1";
  const [win, setWin] = useState<(typeof WINDOWS)[number]>("24h");
  const [brief, setBrief] = useState<Brief | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [openBuried, setOpenBuried] = useState<string | null>(null);

  useEffect(() => {
    setBrief(null); setErr(null);
    api.brief(win, fixture).then(setBrief).catch((e) => setErr(String(e)));
  }, [win, fixture]);

  const matter = brief ? brief.counts.lead + brief.counts.line : 0;

  return (
    <main>
      <header className="sticky top-0 z-30 -mx-4 border-b border-line bg-bg/95 px-4 pb-2 pt-3 backdrop-blur" style={{ top: "env(safe-area-inset-top, 0px)" }}>
        <div className="flex items-center gap-2">
          <h1 className="text-[17px] font-semibold tracking-tight">Brief</h1>
          <div className="ml-auto flex gap-1">
            {WINDOWS.map((w) => (
              <button key={w} onClick={() => setWin(w)} className={`rounded-full px-2.5 py-1 text-[12px] ${w === win ? "bg-fg text-bg" : "border border-line text-muted"}`}>{w}</button>
            ))}
          </div>
        </div>
        <p className="tabular mt-1 text-[12.5px] text-muted">
          {brief ? (<><span className="text-fg">{matter} matter</span> · {brief.counts.buried} buried · ~{brief.minutes_saved} min saved{brief.as_of === "fixture" && " · demo data"}</>) : err ? "API unreachable" : "…"}
        </p>
      </header>

      {err && <p className="mt-6 text-[13px] text-muted">Could not load the brief ({err}). Is the API running?</p>}

      {!brief && !err && (
        <div className="mt-3 space-y-2">{[0, 1, 2].map((i) => <div key={i} className="h-28 animate-pulse rounded-xl border border-line bg-card" />)}</div>
      )}

      {brief && (
        <>
          <section className="mt-3 space-y-2">
            {brief.cards.map((c) => <CardView key={c.id} card={c} compact={c.tier === "line"} />)}
          </section>

          <section className="mt-8 text-center">
            <p className="text-[15px] font-medium">You&apos;re caught up.</p>
            <p className="mt-0.5 text-[12.5px] text-muted">{brief.counts.buried} routine filings buried below.</p>
          </section>

          <section className="mt-5 space-y-1.5">
            {brief.buried.map((g) => (
              <div key={g.category} className="rounded-lg border border-line">
                <button onClick={() => setOpenBuried(openBuried === g.category ? null : g.category)} className="flex w-full items-center px-3 py-2 text-[13px]">
                  <span className="text-muted">{CATEGORY_LABEL[g.category]}</span>
                  <span className="tabular ml-auto text-muted">{g.count}</span>
                </button>
                {openBuried === g.category && (
                  <ul className="border-t border-line px-3 py-1.5 text-[12.5px]">
                    {g.items.map((it) => (
                      <li key={it.id} className="flex gap-2 py-1"><span className="w-20 shrink-0 font-medium">{it.ticker}</span><span className="text-muted">{it.headline}</span></li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </section>
        </>
      )}
    </main>
  );
}

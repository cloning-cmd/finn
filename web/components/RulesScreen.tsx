"use client";
import { useCallback, useEffect, useState } from "react";
import type { Category, Rule, RuleCondition } from "@/lib/types";
type MoveCond = Extract<RuleCondition, { kind: "price_move" }>;
type VolCond = Extract<RuleCondition, { kind: "volume" }>;
type CatCond = Extract<RuleCondition, { kind: "category" }>;
import { CATEGORY_LABEL } from "@/lib/types";
import { api } from "@/lib/api";
import { disablePush, enablePush, pushStatus, type PushStatus } from "@/lib/push";

const CATS: Category[] = ["results", "ma", "fund_raise", "management_change", "litigation", "credit_rating", "dividend", "bonus_split",
  "capex", "pledging", "insider_trading", "earnings_call", "investor_meetings", "press_release", "postal_ballot", "agm_egm"];

function describe(r: Rule): string {
  const c = r.condition;
  const where = r.scope.type === "ticker" ? r.scope.value : "portfolio";
  if (c.kind === "category") return `${c.categories.map((x) => CATEGORY_LABEL[x] ?? x).join(", ")}${c.min_priority ? ` · priority ≥ ${c.min_priority}` : ""} · ${where}`;
  if (c.kind === "price_move") return `${[c.z ? `|z| ≥ ${c.z}` : null, c.pct ? `|move| ≥ ${c.pct}%` : null].filter(Boolean).join(" or ")}${c.direction && c.direction !== "both" ? ` · ${c.direction} only` : ""} · ${where}`;
  if (c.kind === "volume") return `volume ≥ ${c.multiple}× ${c.lookback_days}-day average · ${where}`;
  return `results below guidance${c.min_gap_pct ? ` by ≥ ${c.min_gap_pct}%` : ""} · ${where}`;
}

function Slider({ label, value, min, max, step, unit, onChange }: { label: string; value: number; min: number; max: number; step: number; unit: string; onChange: (v: number) => void }) {
  return (
    <label className="block">
      <div className="flex items-baseline text-[12.5px]"><span className="text-muted">{label}</span><span className="tabular ml-auto">{value}{unit}</span></div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="mt-1 w-full accent-[var(--accent)]" />
    </label>
  );
}

export default function RulesScreen() {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<{ rule: Rule; method: string; cost: number } | null>(null);
  const [parsing, setParsing] = useState(false);
  const [push, setPush] = useState<PushStatus>("off");
  const [pushErr, setPushErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.rules().then(setRules).catch((e) => setErr(String(e))), []);
  useEffect(() => { void load(); void pushStatus().then(setPush); }, [load]);

  const save = useCallback(async (r: Rule) => {
    setRules((rs) => (rs ? rs.map((x) => (x.id === r.id ? r : x)) : rs));
    try { await api.saveRule(r); } catch (e) { setErr(String(e)); void load(); }
  }, [load]);

  const move = rules?.find((r) => r.id === "r_default_move");
  const vol = rules?.find((r) => r.id === "r_default_volume");
  const material = rules?.find((r) => r.id === "r_default_material");
  const custom = rules?.filter((r) => !r.id.startsWith("r_default_")) ?? [];

  const toggleCat = (cat: Category) => {
    if (!material || material.condition.kind !== "category") return;
    const cats = material.condition.categories.includes(cat) ? material.condition.categories.filter((c) => c !== cat) : [...material.condition.categories, cat];
    void save({ ...material, condition: { ...material.condition, categories: cats } });
  };

  const onParse = async () => {
    if (!text.trim()) return;
    setParsing(true); setPreview(null); setErr(null);
    try { setPreview(await api.parseRule(text.trim())); } catch (e) { setErr(String(e)); } finally { setParsing(false); }
  };

  const onSavePreview = async () => {
    if (!preview) return;
    setBusy(true);
    try { await api.saveRule(preview.rule); setPreview(null); setText(""); await load(); } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  const onPush = async () => {
    setPushErr(null);
    if (push === "on") { setPush(await disablePush()); return; }
    const r = await enablePush();
    setPush(r.status); if (r.error) setPushErr(r.error);
  };

  return (
    <main className="pb-6">
      <header className="sticky top-0 z-30 -mx-4 border-b border-line bg-bg/95 px-4 pb-2 pt-3 backdrop-blur" style={{ top: "env(safe-area-inset-top, 0px)" }}>
        <h1 className="text-[17px] font-semibold tracking-tight">Rules</h1>
        <p className="mt-1 text-[12.5px] text-muted">{rules ? `${rules.filter((r) => r.enabled).length} of ${rules.length} on · evaluated on every ingest` : err ? "API unreachable" : "…"}</p>
      </header>

      <section className="mt-4 rounded-xl border border-line bg-card p-3">
        <div className="flex items-center gap-2">
          <div>
            <div className="text-[13.5px] font-medium">Notifications</div>
            <div className="text-[12px] text-muted">
              {push === "on" && "On for this device. A test notification was sent."}
              {push === "off" && "Off. Alerts still land in the inbox."}
              {push === "denied" && "Blocked in browser settings for this site."}
              {push === "unsupported" && "This browser does not support Web Push."}
              {push === "ios_needs_install" && "On iPhone: Share → Add to Home Screen, then open FINN from the icon and enable here."}
            </div>
            {pushErr && <div className="mt-0.5 text-[11.5px] text-down">{pushErr}</div>}
          </div>
          {(push === "on" || push === "off") && (
            <button onClick={onPush} className={`ml-auto shrink-0 rounded-full px-3 py-1 text-[12px] ${push === "on" ? "border border-line text-muted" : "bg-fg text-bg"}`}>{push === "on" ? "Turn off" : "Enable"}</button>
          )}
        </div>
      </section>

      <section className="mt-5">
        <h2 className="text-[11px] uppercase tracking-wide text-muted">Add a rule in plain words</h2>
        <form onSubmit={(e) => { e.preventDefault(); void onParse(); }} className="mt-1.5 flex gap-2">
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Alert me if Infosys falls more than 4%"
                 className="flex-1 rounded-full border border-line bg-card px-3 py-1.5 text-[13px] outline-none focus:border-accent" />
          <button type="submit" disabled={!text.trim() || parsing} className="rounded-full bg-fg px-3 py-1.5 text-[12px] text-bg disabled:opacity-40">{parsing ? "…" : "Preview"}</button>
        </form>
        {preview && (
          <div className="mt-2 rounded-xl border border-accent/60 bg-card p-3">
            <div className="text-[13px] font-medium">{preview.rule.name}</div>
            <div className="mt-0.5 text-[12.5px] text-muted">{describe(preview.rule)}</div>
            <div className="tabular mt-1 text-[11px] text-muted">parsed by {preview.method === "llm" ? `model · ₹${preview.cost.toFixed(2)}` : "rules · ₹0"}</div>
            <div className="mt-2 flex gap-2">
              <button onClick={onSavePreview} disabled={busy} className="rounded-full bg-fg px-3 py-1 text-[12px] text-bg disabled:opacity-40">Save</button>
              <button onClick={() => setPreview(null)} className="rounded-full border border-line px-3 py-1 text-[12px] text-muted">Discard</button>
            </div>
          </div>
        )}
        {err && <p className="mt-2 text-[12px] text-down">{err}</p>}
      </section>

      {rules && move && move.condition.kind === "price_move" && vol && vol.condition.kind === "volume" && material && material.condition.kind === "category" && (
        <>
          <section className="mt-6">
            <div className="flex items-baseline">
              <h2 className="text-[11px] uppercase tracking-wide text-muted">Price and volume</h2>
            </div>
            <div className="mt-2 space-y-3 rounded-xl border border-line bg-card p-3">
              <Toggle label="Unusual price move" on={move.enabled} onChange={(on) => save({ ...move, enabled: on })} />
              <Slider label="Sensitivity (z-score vs 60-day volatility)" value={move.condition.z ?? 2.5} min={1.5} max={4} step={0.25} unit="σ" onChange={(v) => save({ ...move, condition: { ...(move.condition as MoveCond), z: v } })} />
              <Slider label="Or a fixed move of at least" value={move.condition.pct ?? 5} min={2} max={15} step={0.5} unit="%" onChange={(v) => save({ ...move, condition: { ...(move.condition as MoveCond), pct: v } })} />
              <div className="border-t border-line pt-3">
                <Toggle label="Volume spike" on={vol.enabled} onChange={(on) => save({ ...vol, enabled: on })} />
                <Slider label="Volume vs 20-day average" value={vol.condition.multiple} min={1.5} max={5} step={0.25} unit="×" onChange={(v) => save({ ...vol, condition: { ...(vol.condition as VolCond), multiple: v } })} />
              </div>
            </div>
          </section>

          <section className="mt-6">
            <h2 className="text-[11px] uppercase tracking-wide text-muted">Filing categories that alert</h2>
            <div className="mt-2 rounded-xl border border-line bg-card p-3">
              <Toggle label="Material filings" on={material.enabled} onChange={(on) => save({ ...material, enabled: on })} />
              <Slider label="Minimum priority" value={material.condition.min_priority ?? 60} min={30} max={90} step={5} unit="" onChange={(v) => save({ ...material, condition: { ...(material.condition as CatCond), min_priority: v } })} />
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {CATS.map((c) => {
                  const on = material.condition.kind === "category" && material.condition.categories.includes(c);
                  return <li key={c}><button onClick={() => toggleCat(c)} className={`rounded-full px-2.5 py-1 text-[12px] ${on ? "bg-fg text-bg" : "border border-line text-muted"}`}>{CATEGORY_LABEL[c]}</button></li>;
                })}
              </ul>
            </div>
          </section>
        </>
      )}

      {custom.length > 0 && (
        <section className="mt-6">
          <h2 className="text-[11px] uppercase tracking-wide text-muted">Your rules</h2>
          <ul className="mt-2 space-y-2">
            {custom.map((r) => (
              <li key={r.id} className="rounded-xl border border-line bg-card p-3">
                <Toggle label={r.name} on={r.enabled} onChange={(on) => save({ ...r, enabled: on })} />
                <div className="mt-0.5 text-[12px] text-muted">{describe(r)}</div>
                {r.source_text && <div className="mt-0.5 text-[11.5px] text-muted">“{r.source_text}”</div>}
                <button onClick={async () => { await api.deleteRule(r.id).catch(() => undefined); void load(); }} className="mt-2 text-[11.5px] text-muted underline-offset-2 hover:underline">Delete</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!rules && !err && <div className="mt-4 space-y-2">{[0, 1].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl border border-line bg-card" />)}</div>}
    </main>
  );
}

function Toggle({ label, on, onChange }: { label: string; on: boolean; onChange: (on: boolean) => void }) {
  return (
    <div className="flex items-center">
      <span className="text-[13.5px] font-medium">{label}</span>
      <button role="switch" aria-checked={on} onClick={() => onChange(!on)} className={`ml-auto h-6 w-10 rounded-full p-0.5 transition-colors ${on ? "bg-accent" : "bg-line"}`}>
        <span className={`block h-5 w-5 rounded-full bg-bg transition-transform ${on ? "translate-x-4" : ""}`} />
      </button>
    </div>
  );
}

"use client";
import { useCallback, useEffect, useState } from "react";
import type { Category, Rule, RuleCondition } from "@/lib/types";
import { CATEGORY_LABEL } from "@/lib/types";
import { api } from "@/lib/api";
import { disablePush, enablePush, pushStatus, type PushStatus } from "@/lib/push";
import { Badge, Button, Icon, PageHeader, SectionLabel, Skeleton, Spinner, cx } from "@/components/ui";

type MoveCond = Extract<RuleCondition, { kind: "price_move" }>;
type VolCond = Extract<RuleCondition, { kind: "volume" }>;
type CatCond = Extract<RuleCondition, { kind: "category" }>;

const CATS: Category[] = ["results", "ma", "fund_raise", "management_change", "litigation", "credit_rating", "dividend", "bonus_split",
  "capex", "pledging", "insider_trading", "earnings_call", "investor_meetings", "press_release", "postal_ballot", "agm_egm"];
const EXAMPLES = ["Alert me if Infosys falls more than 4%", "Any credit rating change", "Volume over 3x for TITAN"];

function describe(r: Rule): string {
  const c = r.condition;
  const where = r.scope.type === "ticker" ? r.scope.value : "all holdings";
  if (c.kind === "category") return `${c.categories.map((x) => CATEGORY_LABEL[x] ?? x).join(", ")}${c.min_priority ? ` · priority ${c.min_priority}+` : ""} · ${where}`;
  if (c.kind === "price_move") return `${[c.z ? `${c.z}σ move` : null, c.pct ? `${c.pct}% move` : null].filter(Boolean).join(" or ")}${c.direction && c.direction !== "both" ? ` · ${c.direction} only` : ""} · ${where}`;
  if (c.kind === "volume") return `Volume ${c.multiple}× the ${c.lookback_days}-day average · ${where}`;
  return `Results below guidance${c.min_gap_pct ? ` by ${c.min_gap_pct}%+` : ""} · ${where}`;
}

function Toggle({ on, onChange, label }: { on: boolean; onChange: (on: boolean) => void; label: string }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}
      className={cx("relative h-[26px] w-[44px] shrink-0 rounded-full transition-colors", on ? "bg-accent" : "bg-line-strong")}>
      <span className={cx("absolute left-[3px] top-[3px] h-5 w-5 rounded-full bg-white shadow transition-transform", on && "translate-x-[18px]")} />
    </button>
  );
}

function Slider({ label, value, min, max, step, unit, onChange, disabled }: {
  label: string; value: number; min: number; max: number; step: number; unit: string; onChange: (v: number) => void; disabled?: boolean;
}) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <label className={cx("block", disabled && "opacity-40")}>
      <div className="flex items-baseline text-[13px]"><span className="text-muted">{label}</span><span className="tabular ml-auto font-semibold">{value}{unit}</span></div>
      <input type="range" min={min} max={max} step={step} value={value} disabled={disabled} onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 h-1.5 w-full cursor-pointer appearance-none rounded-full accent-[var(--accent)]"
        style={{ background: `linear-gradient(to right, var(--accent) ${pct}%, var(--line-strong) ${pct}%)` }} />
    </label>
  );
}

function Setting({ title, sub, on, onToggle, children }: { title: string; sub: string; on: boolean; onToggle: (on: boolean) => void; children?: React.ReactNode }) {
  return (
    <li className="px-4 py-3.5">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1"><div className="text-[14px] font-medium">{title}</div><div className="text-[12px] text-muted">{sub}</div></div>
        <Toggle on={on} onChange={onToggle} label={title} />
      </div>
      {children && <div className="mt-4 space-y-4">{children}</div>}
    </li>
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

  const load = useCallback(() => api.rules().then((r) => { setRules(r); setErr(null); }).catch((e) => setErr(String(e))), []);
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

  const onParse = async (t = text) => {
    if (!t.trim()) return;
    setParsing(true); setPreview(null); setErr(null);
    try { setPreview(await api.parseRule(t.trim())); } catch (e) { setErr(String(e)); } finally { setParsing(false); }
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

  const pushSub: Record<PushStatus, string> = {
    on: "On for this device", off: "Alerts still land in the inbox",
    denied: "Blocked in this browser's site settings", unsupported: "This browser does not support Web Push",
    ios_needs_install: "On iPhone: Share, Add to Home Screen, then open FINN from the icon",
  };

  return (
    <main>
      <PageHeader title="Rules" eyebrow={rules ? `${rules.filter((r) => r.enabled).length} of ${rules.length} active · checked on every update` : err ? "API unreachable" : "Loading"} />

      <section className="surface mt-1 flex items-center gap-3 rounded-2xl p-4">
        <span className={cx("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", push === "on" ? "bg-up/12 text-up" : "bg-accent/12 text-accent")}><Icon name="bell" size={19} /></span>
        <div className="min-w-0 flex-1">
          <div className="text-[14px] font-medium">Push notifications</div>
          <div className="text-[12px] text-muted">{pushSub[push]}</div>
          {pushErr && <div className="mt-0.5 text-[12px] text-down">{pushErr}</div>}
        </div>
        {(push === "on" || push === "off") && <Button size="sm" variant={push === "on" ? "secondary" : "primary"} onClick={onPush}>{push === "on" ? "Turn off" : "Enable"}</Button>}
      </section>

      <SectionLabel>New rule</SectionLabel>
      <section className="surface rounded-2xl p-4">
        <form onSubmit={(e) => { e.preventDefault(); void onParse(); }} className="flex items-center gap-2">
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Describe it in plain words" aria-label="Describe a rule"
            className="h-11 min-w-0 flex-1 rounded-xl bg-surface-2 px-3 text-[14px] outline-none placeholder:text-faint focus:ring-2 focus:ring-accent/50" />
          <Button type="submit" disabled={!text.trim() || parsing} className="h-11">{parsing ? <Spinner size={14} /> : "Preview"}</Button>
        </form>
        {!preview && (
          <div className="no-scrollbar -mx-4 mt-3 flex gap-1.5 overflow-x-auto px-4">
            {EXAMPLES.map((ex) => (
              <button key={ex} onClick={() => { setText(ex); void onParse(ex); }} className="shrink-0 rounded-lg border border-line px-2.5 py-1.5 text-[12px] text-muted transition-colors hover:border-accent/50 hover:text-fg">{ex}</button>
            ))}
          </div>
        )}
        {preview && (
          <div className="mt-3 rounded-xl border border-accent/40 bg-accent/[0.06] p-3">
            <div className="flex items-center gap-2">
              <span className="text-[14px] font-medium">{preview.rule.name}</span>
              <Badge className="ml-auto">{preview.method === "llm" ? `model · ₹${preview.cost.toFixed(2)}` : "rules · ₹0"}</Badge>
            </div>
            <div className="mt-1 text-[12.5px] text-muted">{describe(preview.rule)}</div>
            <div className="mt-3 flex gap-2">
              <Button size="sm" onClick={onSavePreview} disabled={busy}>Save rule</Button>
              <Button size="sm" variant="ghost" onClick={() => setPreview(null)}>Discard</Button>
            </div>
          </div>
        )}
        {err && <p className="mt-2 text-[12.5px] text-down">{err}</p>}
      </section>

      {!rules && !err && <div className="mt-6 space-y-3"><Skeleton className="h-40" /><Skeleton className="h-32" /></div>}

      {custom.length > 0 && (
        <>
          <SectionLabel right={custom.length}>Your rules</SectionLabel>
          <ul className="surface divide-y divide-line overflow-hidden rounded-2xl">
            {custom.map((r) => (
              <li key={r.id} className="px-4 py-3.5">
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-[14px] font-medium">{r.name}</div>
                    <div className="mt-0.5 text-[12px] text-muted">{describe(r)}</div>
                  </div>
                  <Toggle on={r.enabled} onChange={(on) => save({ ...r, enabled: on })} label={r.name} />
                </div>
                <button onClick={async () => { await api.deleteRule(r.id).catch(() => undefined); void load(); }}
                  className="mt-2 text-[12px] font-medium text-down/80 hover:text-down">Delete</button>
              </li>
            ))}
          </ul>
        </>
      )}

      {rules && move && move.condition.kind === "price_move" && vol && vol.condition.kind === "volume" && material && material.condition.kind === "category" && (
        <>
          <SectionLabel>Price and volume</SectionLabel>
          <ul className="surface divide-y divide-line overflow-hidden rounded-2xl">
            <Setting title="Unusual price move" sub="Measured against each stock's own 60-day volatility" on={move.enabled} onToggle={(on) => save({ ...move, enabled: on })}>
              <Slider label="Sensitivity" value={move.condition.z ?? 2.5} min={1.5} max={4} step={0.25} unit="σ" disabled={!move.enabled}
                onChange={(v) => save({ ...move, condition: { ...(move.condition as MoveCond), z: v } })} />
              <Slider label="Or a fixed move of" value={move.condition.pct ?? 5} min={2} max={15} step={0.5} unit="%" disabled={!move.enabled}
                onChange={(v) => save({ ...move, condition: { ...(move.condition as MoveCond), pct: v } })} />
            </Setting>
            <Setting title="Volume spike" sub="Compared with the 20-day average" on={vol.enabled} onToggle={(on) => save({ ...vol, enabled: on })}>
              <Slider label="Threshold" value={vol.condition.multiple} min={1.5} max={5} step={0.25} unit="×" disabled={!vol.enabled}
                onChange={(v) => save({ ...vol, condition: { ...(vol.condition as VolCond), multiple: v } })} />
            </Setting>
          </ul>

          <SectionLabel>Filings</SectionLabel>
          <ul className="surface divide-y divide-line overflow-hidden rounded-2xl">
            <Setting title="Material filings" sub="Alert when a filing in these categories scores above the bar" on={material.enabled} onToggle={(on) => save({ ...material, enabled: on })}>
              <Slider label="Minimum priority" value={material.condition.min_priority ?? 60} min={30} max={90} step={5} unit="" disabled={!material.enabled}
                onChange={(v) => save({ ...material, condition: { ...(material.condition as CatCond), min_priority: v } })} />
              <div className="flex flex-wrap gap-1.5">
                {CATS.map((c) => {
                  const on = material.condition.kind === "category" && material.condition.categories.includes(c);
                  return (
                    <button key={c} onClick={() => toggleCat(c)} aria-pressed={on}
                      className={cx("inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[12.5px] font-medium transition-colors",
                        on ? "bg-accent/14 text-accent" : "bg-surface-2 text-muted hover:text-fg")}>
                      {on && <Icon name="check" size={12} strokeWidth={2.6} />}{CATEGORY_LABEL[c]}
                    </button>
                  );
                })}
              </div>
            </Setting>
          </ul>
        </>
      )}
    </main>
  );
}

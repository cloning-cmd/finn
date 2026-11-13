"use client";
// Shared building blocks: page header, segmented control, ticker avatar, badges, panels, stats, empty states.
import type { ReactNode } from "react";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/** Sticky large-title header. `eyebrow` sits above the title; `right` aligns with it; children render below. */
export function PageHeader({ title, eyebrow, right, children }: { title: ReactNode; eyebrow?: ReactNode; right?: ReactNode; children?: ReactNode }) {
  return (
    <header className="sticky top-0 z-30 -mx-4 bg-bg/85 px-4 pb-3 pt-4 backdrop-blur-xl md:-mx-6 md:px-6" style={{ top: "env(safe-area-inset-top, 0px)" }}>
      <div className="flex items-end gap-3">
        <div className="min-w-0">
          {eyebrow && <div className="text-[12px] font-medium text-muted">{eyebrow}</div>}
          <h1 className="truncate text-[26px] font-semibold leading-tight tracking-[-0.02em]">{title}</h1>
        </div>
        {right && <div className="ml-auto flex shrink-0 items-center gap-2 pb-0.5">{right}</div>}
      </div>
      {children && <div className="mt-3">{children}</div>}
    </header>
  );
}

export function Segmented<T extends string>({ options, value, onChange, labels, className }: {
  options: readonly T[]; value: T; onChange: (v: T) => void; labels?: Partial<Record<T, string>>; className?: string;
}) {
  return (
    <div role="tablist" className={cx("flex rounded-xl bg-surface-2 p-1", className)}>
      {options.map((o) => (
        <button key={o} role="tab" aria-selected={o === value} onClick={() => onChange(o)}
          className={cx("flex-1 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors",
            o === value ? "bg-surface text-fg shadow-[var(--shadow)]" : "text-muted hover:text-fg")}>
          {labels?.[o] ?? o}
        </button>
      ))}
    </div>
  );
}

const AVATAR_HUES = [222, 262, 192, 152, 32, 340, 280, 202, 12, 172];
/** Monogram tile for a ticker; the hue is stable per symbol so a company is recognisable across screens. */
export function TickerAvatar({ ticker, size = 36 }: { ticker: string; size?: number }) {
  let h = 0;
  for (const ch of ticker) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const hue = AVATAR_HUES[h % AVATAR_HUES.length];
  const letters = ticker.replace(/[^A-Z0-9]/gi, "").slice(0, 2).toUpperCase();
  return (
    <span aria-hidden="true" className="inline-flex shrink-0 items-center justify-center rounded-[10px] font-semibold tracking-tight"
      style={{ width: size, height: size, fontSize: size * 0.36, color: `hsl(${hue} 65% var(--avatar-l))`, background: `hsl(${hue} 60% 55% / 0.14)` }}>
      {letters}
    </span>
  );
}

export function PersonAvatar({ name, size = 32 }: { name: string; size?: number }) {
  const parts = name.replace(/[^A-Za-z ]/g, " ").split(/\s+/).filter((p) => p.length > 1);
  const ini = ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
  return (
    <span aria-hidden="true" className="inline-flex shrink-0 items-center justify-center rounded-full bg-line font-medium text-fg/80"
      style={{ width: size, height: size, fontSize: size * 0.38 }}>{ini || "?"}</span>
  );
}

type Tone = "neutral" | "accent" | "up" | "down" | "warn";
const TONE: Record<Tone, string> = {
  neutral: "bg-surface-2 text-muted",
  accent: "bg-accent/12 text-accent",
  up: "bg-up/12 text-up",
  down: "bg-down/12 text-down",
  warn: "bg-warn/14 text-warn",
};
export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={cx("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium leading-none", TONE[tone], className)}>{children}</span>;
}

/** A titled surface block. */
export function Panel({ title, action, children, className, pad = true }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={cx("surface rounded-2xl", pad && "p-4", className)}>
      {(title || action) && (
        <div className={cx("mb-3 flex items-center gap-2", !pad && "px-4 pt-4")}>
          {title && <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>}
          {action && <div className="ml-auto text-[12.5px] text-muted">{action}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function SectionLabel({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-2 mt-6 flex items-baseline px-1">
      <h2 className="text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">{children}</h2>
      {right && <div className="ml-auto text-[12px] text-muted">{right}</div>}
    </div>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "up" | "down" }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-[11.5px] text-muted">{label}</div>
      <div className={cx("tabular mt-0.5 truncate text-[17px] font-semibold tracking-tight", tone === "up" && "text-up", tone === "down" && "text-down")}>{value}</div>
      {sub && <div className="tabular mt-0.5 truncate text-[11.5px] text-muted">{sub}</div>}
    </div>
  );
}

/** Inset grouped list (settings style). Children should be <Row>s. */
export function List({ children, className }: { children: ReactNode; className?: string }) {
  return <ul className={cx("surface divide-y divide-line overflow-hidden rounded-2xl", className)}>{children}</ul>;
}
export function Row({ children, onClick, href, className }: { children: ReactNode; onClick?: () => void; href?: string; className?: string }) {
  const cls = cx("flex w-full items-center gap-3 px-4 py-3 text-left", (onClick || href) && "transition-colors hover:bg-surface-2 active:bg-surface-2", className);
  if (href) return <li><a href={href} target="_blank" rel="noopener noreferrer" className={cls}>{children}</a></li>;
  if (onClick) return <li><button onClick={onClick} className={cls}>{children}</button></li>;
  return <li className={cls}>{children}</li>;
}

export function Empty({ icon, title, body, action }: { icon?: ReactNode; title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      {icon && <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-surface-2 text-muted">{icon}</div>}
      <p className="text-[15px] font-semibold">{title}</p>
      {body && <p className="mt-1 max-w-xs text-[13px] text-muted">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-2xl bg-surface-2", className)} />;
}

export function Button({ children, onClick, variant = "primary", disabled, type = "button", className, size = "md" }: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "ghost"; disabled?: boolean; type?: "button" | "submit"; className?: string; size?: "sm" | "md";
}) {
  const v = variant === "primary" ? "bg-accent text-accent-fg hover:opacity-90" : variant === "secondary" ? "bg-surface-2 text-fg hover:bg-line" : "text-muted hover:text-fg";
  const s = size === "sm" ? "h-8 px-3 text-[12.5px]" : "h-10 px-4 text-[13.5px]";
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={cx("inline-flex shrink-0 items-center justify-center gap-1.5 rounded-xl font-medium transition disabled:opacity-40", v, s, className)}>
      {children}
    </button>
  );
}

/** Small stroked icons (24-grid paths). */
const ICONS = {
  search: "M21 21l-4.3-4.3M17 10.5a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0z",
  check: "M5 12.5l4.5 4.5L19 7.5",
  chevron: "M9 6l6 6-6 6",
  down: "M6 9l6 6 6-6",
  arrowUp: "M12 19V5M5.5 11.5L12 5l6.5 6.5",
  send: "M5 12h14M13 6l6 6-6 6",
  doc: "M7 3h7l5 5v13H7zM14 3v5h5",
  bell: "M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 0 0-4-5.7V5a2 2 0 1 0-4 0v.3A6 6 0 0 0 6 11v3.2c0 .5-.2 1-.6 1.4L4 17h5m6 0v1a3 3 0 1 1-6 0v-1",
  spark: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6",
  play: "M8 5v14l11-7z",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
  x: "M6 6l12 12M18 6L6 18",
  clock: "M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  inbox: "M4 13h4l1.5 3h5L16 13h4M5.5 5h13L21 13v6H3v-6z",
} as const;
export type IconName = keyof typeof ICONS;
export function Icon({ name, size = 18, className, strokeWidth = 1.8 }: { name: IconName; size?: number; className?: string; strokeWidth?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

export function Spinner({ size = 16 }: { size?: number }) {
  return <span aria-hidden="true" className="inline-block animate-spin rounded-full border-2 border-line border-t-accent" style={{ width: size, height: size }} />;
}

/** "BAJFINANCE: Outcome of QIP" → "Outcome of QIP" when the ticker is already shown next to it. */
export function stripTicker(headline: string, ticker: string): string {
  const h = headline.trim();
  for (const pre of [`${ticker}: `, `${ticker} `]) {
    if (h.toUpperCase().startsWith(pre.toUpperCase())) {
      const rest = h.slice(pre.length);
      return rest.charAt(0).toUpperCase() + rest.slice(1);
    }
  }
  return h;
}

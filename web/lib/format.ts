// Number/date formatting. Indian grouping for ₹ Cr, signed % and bps.
const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const inr1 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export const fmtCr = (v: number) => (Math.abs(v) >= 1000 ? inr.format(Math.round(v)) : inr1.format(v));
export const fmtPct = (v: number, dp = 1) => `${v > 0 ? "+" : ""}${v.toFixed(dp)}%`;
export const fmtBps = (v: number) => `${v > 0 ? "+" : ""}${Math.round(v)} bps`;
export const fmtX = (v: number) => `${v.toFixed(1)}×`;
export const fmtVol = (v: number) => (v >= 1e7 ? `${(v / 1e7).toFixed(1)} Cr` : v >= 1e5 ? `${(v / 1e5).toFixed(1)} L` : inr.format(v));

export function fmtWhen(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const mins = Math.round((now.getTime() - d.getTime()) / 60000);
  if (mins < 60) return `${Math.max(mins, 0)}m`;
  const h = Math.round(mins / 60);
  if (h < 24) return `${h}h`;
  const days = Math.round(h / 24);
  if (days < 7) return `${days}d`;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export const dirClass = (v: number) => (v > 0 ? "text-up" : v < 0 ? "text-down" : "text-muted");

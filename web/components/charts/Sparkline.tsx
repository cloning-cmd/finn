import { useId } from "react";

/** Line + soft area fill. Colour carries direction only (green up / red down). */
export default function Sparkline({ values, className = "", positive = true }: { values: number[]; className?: string; positive?: boolean }) {
  const gid = useId().replace(/:/g, "");
  if (!values.length) return null;
  const w = 100, h = 32, pad = 2;
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const n = Math.max(values.length - 1, 1);
  const pts = values.map((v, i) => [pad + (i / n) * (w - 2 * pad), pad + (1 - (v - min) / span) * (h - 2 * pad)] as const);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${d} L${pts[pts.length - 1][0].toFixed(1)},${h} L${pts[0][0].toFixed(1)},${h} Z`;
  const col = positive ? "var(--up)" : "var(--down)";
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={gid} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={col} stopOpacity="0.22" />
          <stop offset="100%" stopColor={col} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={d} fill="none" stroke={col} strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}

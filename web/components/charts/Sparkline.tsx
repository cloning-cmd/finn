export default function Sparkline({ values, className = "", positive = true }: { values: number[]; className?: string; positive?: boolean }) {
  if (!values.length) return null;
  const w = 100, h = 32, pad = 2;
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const pts = values.map((v, i) => [pad + (i / (values.length - 1)) * (w - 2 * pad), pad + (1 - (v - min) / span) * (h - 2 * pad)] as const);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={className} aria-hidden="true">
      <path d={d} fill="none" stroke={positive ? "var(--up)" : "var(--down)"} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      <circle cx={last[0]} cy={last[1]} r="2" fill={positive ? "var(--up)" : "var(--down)"} />
    </svg>
  );
}

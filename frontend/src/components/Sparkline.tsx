interface Point {
  q: number;
  forecast: boolean;
}

/** Last 30 days solid, next 7 days dashed, today as a dot. */
export function Sparkline({ series, color, width = 132, height = 34 }: { series: Point[]; color: string; width?: number; height?: number }) {
  if (series.length < 2) return null;
  const qs = series.map((p) => p.q);
  const lo = Math.min(...qs);
  const hi = Math.max(...qs);
  const x = (i: number) => (i / (series.length - 1)) * (width - 4) + 2;
  const y = (q: number) => height - 3 - ((q - lo) / (hi - lo || 1)) * (height - 6);
  const todayIdx = series.findIndex((p) => p.forecast) - 1;
  const cut = todayIdx >= 0 ? todayIdx : series.length - 1;
  const path = (from: number, to: number) =>
    series
      .slice(from, to + 1)
      .map((p, k) => `${k ? "L" : "M"}${x(from + k).toFixed(1)},${y(p.q).toFixed(1)}`)
      .join("");

  return (
    <svg className="spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={path(0, cut)} fill="none" stroke="var(--river)" strokeWidth={1.6} />
      {cut < series.length - 1 && (
        <path d={path(cut, series.length - 1)} fill="none" stroke="var(--river)" strokeWidth={1.6} strokeDasharray="3 2" opacity={0.7} />
      )}
      <circle cx={x(cut)} cy={y(series[cut].q)} r={3} fill={color} stroke="#fff" strokeWidth={1} />
    </svg>
  );
}

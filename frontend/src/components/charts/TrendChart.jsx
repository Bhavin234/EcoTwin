import { useId, useMemo } from "react";
import "./TrendChart.css";

/**
 * A small, dependency-free SVG line chart (docs Milestone 6, requirement
 * #2: "avoid unnecessary dependencies"). For the dataset sizes this app
 * ever renders (a few dozen to a few hundred points), a hand-rolled SVG
 * path gives full control over the restrained, non-"AI gimmick" look the
 * brief calls for without adding a charting library as a dependency.
 *
 * `series`: [{ label, color, points: [{x: Date|number, y: number}] }]
 * `markers`: optional [{ x, label, color }] vertical reference lines (e.g.
 * an anomaly window or intervention point).
 */
export default function TrendChart({ series, markers = [], height = 220, yLabel, formatX, formatY }) {
  const gradientId = useId();
  const width = 720;
  const padding = { top: 16, right: 16, bottom: 28, left: 48 };

  const { xScale, yScale, xTicks, yTicks } = useMemo(() => {
    const allPoints = series.flatMap((s) => s.points);
    if (allPoints.length === 0) {
      return { xScale: () => 0, yScale: () => 0, xTicks: [], yTicks: [] };
    }
    const xs = allPoints.map((p) => +p.x);
    const ys = allPoints.map((p) => p.y);
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    const yMin = Math.min(0, ...ys);
    const yMax = Math.max(...ys) * 1.1 || 1;

    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;

    const xScale = (x) => padding.left + ((x - xMin) / (xMax - xMin || 1)) * innerWidth;
    const yScale = (y) => padding.top + innerHeight - ((y - yMin) / (yMax - yMin || 1)) * innerHeight;

    const xTicks = [xMin, xMin + (xMax - xMin) / 2, xMax];
    const yTicks = [yMin, yMin + (yMax - yMin) / 2, yMax];

    return { xScale, yScale, xTicks, yTicks };
  }, [series, height]);

  if (series.every((s) => s.points.length === 0)) {
    return <p className="trend-chart__empty">No telemetry available for this range yet.</p>;
  }

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label={yLabel || "Trend chart"}>
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={padding.left} x2={width - padding.right} y1={yScale(t)} y2={yScale(t)} className="trend-chart__gridline" />
          <text x={padding.left - 8} y={yScale(t)} className="trend-chart__axis-label" textAnchor="end" dominantBaseline="middle">
            {formatY ? formatY(t) : Math.round(t)}
          </text>
        </g>
      ))}

      {markers.map((m, i) => (
        <g key={i}>
          <line x1={xScale(+m.x)} x2={xScale(+m.x)} y1={padding.top} y2={height - padding.bottom} className="trend-chart__marker" stroke={m.color} />
          <text x={xScale(+m.x)} y={padding.top - 4} className="trend-chart__marker-label" fill={m.color} textAnchor="middle">
            {m.label}
          </text>
        </g>
      ))}

      {series.map((s, i) => {
        const path = s.points
          .map((p, idx) => `${idx === 0 ? "M" : "L"} ${xScale(+p.x)} ${yScale(p.y)}`)
          .join(" ");
        return <path key={i} d={path} fill="none" stroke={s.color} strokeWidth={2} />;
      })}

      {xTicks.map((t, i) => (
        <text key={i} x={xScale(t)} y={height - padding.bottom + 16} className="trend-chart__axis-label" textAnchor="middle">
          {formatX ? formatX(t) : ""}
        </text>
      ))}

      <line x1={padding.left} x2={width - padding.right} y1={height - padding.bottom} y2={height - padding.bottom} className="trend-chart__axis-line" />
    </svg>
  );
}

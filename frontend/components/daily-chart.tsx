/**
 * Günlük net kâr alan grafiği — handoff `Dashboard.dc.html`.
 *
 * İki seri üst üste çizilir:
 * - **kesin**: `#16A34A` 1.8px düz çizgi + `rgba(22,163,74,0.15)` dolgu
 * - **toplam (tahmini dahil)**: kesikli `rgba(22,163,74,0.45)` çizgi + `0.07` dolgu
 *
 * Aradaki bant "henüz kesinleşmemiş kâr"dır ve son günlerde doğal olarak genişler —
 * kargo faturası ve hakediş sonradan gelir. Bu ayrım ürünün DNA'sı olduğu için grafikte
 * de görünür, yalnız KPI'da değil.
 *
 * Ek bağımlılık yok: düz SVG. Kütüphane getirmek bu sadelikte kazanç sağlamazdı.
 */

import { formatDayShort, formatMoneyWhole, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

export type DailyPoint = { day: string; profit: string; final_profit: string };

const WIDTH = 720;
const HEIGHT = 260;
const PADDING = { top: 12, right: 8, bottom: 22, left: 52 };

export function DailyProfitChart({ points }: { points: DailyPoint[] }) {
  if (points.length === 0) return null;

  const totals = points.map((point) => toNumber(point.profit));
  const finals = points.map((point) => toNumber(point.final_profit));
  const max = Math.max(...totals, ...finals, 0);
  const min = Math.min(...totals, ...finals, 0);
  const span = max - min || 1;

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const stepX = points.length > 1 ? plotWidth / (points.length - 1) : 0;

  const x = (index: number) => PADDING.left + index * stepX;
  const y = (value: number) => PADDING.top + (1 - (value - min) / span) * plotHeight;
  const baseline = y(Math.max(0, min));

  const line = (values: number[]) =>
    values.map((value, index) => `${index === 0 ? "M" : "L"}${x(index)},${y(value)}`).join(" ");
  const area = (values: number[]) =>
    `${line(values)} L${x(values.length - 1)},${baseline} L${x(0)},${baseline} Z`;

  // Yatay gridline'lar: sıfır çizgisi dahil dört seviye.
  const levels = [0, 0.25, 0.5, 0.75, 1].map((ratio) => min + span * ratio);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-end gap-4 text-micro text-ink-body">
        <Legend color="#16A34A" label={tr.dashboard.legendFinal} />
        <Legend color="rgba(22,163,74,0.45)" label={tr.dashboard.legendTotal} dashed />
      </div>

      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-[260px] w-full"
        role="img"
        aria-label={tr.dashboard.dailyTitle}
      >
        {levels.map((value) => (
          <g key={value}>
            <line
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={y(value)}
              y2={y(value)}
              stroke="#E7E5E4"
              strokeWidth={1}
              strokeDasharray="3 3"
            />
            <text x={PADDING.left - 8} y={y(value) + 3} textAnchor="end" className="fill-ink-muted text-[11px]">
              {formatMoneyWhole(value)}
            </text>
          </g>
        ))}

        <path d={area(totals)} fill="rgba(22,163,74,0.07)" />
        <path d={area(finals)} fill="rgba(22,163,74,0.15)" />
        <path
          d={line(totals)}
          fill="none"
          stroke="rgba(22,163,74,0.45)"
          strokeWidth={1.8}
          strokeDasharray="4 3"
        />
        <path d={line(finals)} fill="none" stroke="#16A34A" strokeWidth={1.8} />

        <text x={PADDING.left} y={HEIGHT - 4} className="fill-ink-muted text-[11px]">
          {formatDayShort(points[0].day)}
        </text>
        <text
          x={WIDTH - PADDING.right}
          y={HEIGHT - 4}
          textAnchor="end"
          className="fill-ink-muted text-[11px]"
        >
          {formatDayShort(points[points.length - 1].day)}
        </text>
      </svg>
    </div>
  );
}

function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <svg width="14" height="6" aria-hidden>
        <line
          x1="0"
          y1="3"
          x2="14"
          y2="3"
          stroke={color}
          strokeWidth={1.8}
          strokeDasharray={dashed ? "4 3" : undefined}
        />
      </svg>
      {label}
    </span>
  );
}

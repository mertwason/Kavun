/**
 * Kâr şelalesi — ürünün imza görseli (tasarım brief'i, kalıp 4).
 *
 * Satış fiyatından net kâra inen adımlar. Recharts yerine düz SVG: grafik bu
 * sadelikte kaldığı sürece ek bağımlılık taşımaya değmez (brief: "Recharts ile
 * uygulanabilir sadelikte tut").
 *
 * Sunucu bileşeni — etkileşim yok, hover bilgisi `<title>` ile erişilebilir.
 */

import type { WaterfallStep } from "@/lib/api";
import { formatMoney, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

const LABELS: Record<string, string> = tr.waterfall;

const ROW_HEIGHT = 34;
const BAR_HEIGHT = 18;
const LABEL_WIDTH = 132;
const VALUE_WIDTH = 116;

export function Waterfall({ steps }: { steps: WaterfallStep[] }) {
  // Sıfır adımlar gösterilmez (reklam payı Faz 4'e kadar hep sıfır) ama satış ve
  // kâr her zaman durur — şelalenin başı ve sonu görünmeli.
  const visible = steps.filter(
    (step) => toNumber(step.amount) !== 0 || step.key === "satis" || step.key === "kar",
  );
  if (visible.length === 0) {
    return null;
  }

  // Kümülatif konumlar: her adım bir öncekinin bıraktığı yerden başlar.
  let running = 0;
  const bars = visible.map((step) => {
    const amount = toNumber(step.amount);
    const isTotal = step.key === "kar";
    const start = isTotal ? 0 : running;
    const end = isTotal ? amount : running + amount;
    if (!isTotal) running = end;
    return { key: step.key, amount, start, end, isTotal };
  });

  const bounds = bars.flatMap((bar) => [bar.start, bar.end]);
  const min = Math.min(0, ...bounds);
  const max = Math.max(0, ...bounds);
  const span = max - min || 1;

  const plotWidth = 100; // yüzde tabanlı; SVG viewBox ile ölçeklenir
  const scale = (value: number) => ((value - min) / span) * plotWidth;
  const height = bars.length * ROW_HEIGHT;

  return (
    <svg
      viewBox={`0 0 ${LABEL_WIDTH + plotWidth + VALUE_WIDTH} ${height}`}
      className="w-full"
      role="img"
      aria-label={tr.chart.waterfallTitle}
    >
      {bars.map((bar, index) => {
        const y = index * ROW_HEIGHT;
        const left = LABEL_WIDTH + Math.min(scale(bar.start), scale(bar.end));
        const width = Math.max(Math.abs(scale(bar.end) - scale(bar.start)), 0.6);
        const fill = bar.isTotal
          ? bar.amount < 0
            ? "#B91C1C"
            : "#1C1917"
          : bar.amount < 0
            ? "#B91C1C"
            : "#15803D";
        return (
          <g key={bar.key}>
            <title>{`${LABELS[bar.key] ?? bar.key}: ${formatMoney(bar.amount)}`}</title>
            <text
              x={LABEL_WIDTH - 8}
              y={y + BAR_HEIGHT}
              textAnchor="end"
              className="fill-ink-muted text-[11px]"
            >
              {LABELS[bar.key] ?? bar.key}
            </text>
            <rect
              x={left}
              y={y + 5}
              width={width}
              height={BAR_HEIGHT}
              rx={1.5}
              fill={fill}
              fillOpacity={bar.isTotal ? 1 : 0.85}
            />
            <text
              x={LABEL_WIDTH + plotWidth + VALUE_WIDTH - 4}
              y={y + BAR_HEIGHT}
              textAnchor="end"
              className={`text-[11px] tabular ${
                bar.isTotal ? "fill-ink font-medium" : "fill-ink-muted"
              }`}
            >
              {formatMoney(bar.amount)}
            </text>
          </g>
        );
      })}
      {/* Sıfır çizgisi: negatif adımların nereden başladığı görünsün. */}
      <line
        x1={LABEL_WIDTH + scale(0)}
        x2={LABEL_WIDTH + scale(0)}
        y1={0}
        y2={height}
        stroke="#E7E5E4"
        strokeWidth={0.5}
      />
    </svg>
  );
}

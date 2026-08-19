/**
 * Günlük kâr grafiği — dashboard'ın tek grafiği (brief: "her görsel bir soruya cevap
 * vermeli"). Soru: "kâr hangi günlerde negatife düştü?"
 *
 * Düz SVG sütun grafiği; sıfır çizgisinin altındaki sütunlar kırmızı.
 */

import type { Dashboard } from "@/lib/api";
import { formatDayShort, formatMoney, toNumber } from "@/lib/format";

const HEIGHT = 120;
const GAP = 1.5;

export function DailyProfitChart({ points }: { points: Dashboard["daily"] }) {
  if (points.length === 0) {
    return null;
  }

  const values = points.map((point) => toNumber(point.profit));
  const max = Math.max(0, ...values);
  const min = Math.min(0, ...values);
  const span = max - min || 1;
  const zeroY = (max / span) * HEIGHT;
  const width = points.length * (4 + GAP);

  return (
    <div className="flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${width} ${HEIGHT}`}
        preserveAspectRatio="none"
        className="h-32 w-full"
        role="img"
        aria-label="Günlük kâr"
      >
        <line x1={0} x2={width} y1={zeroY} y2={zeroY} stroke="#E7E5E4" strokeWidth={0.5} />
        {points.map((point, index) => {
          const value = toNumber(point.profit);
          const barHeight = Math.max((Math.abs(value) / span) * HEIGHT, 0.5);
          const y = value >= 0 ? zeroY - barHeight : zeroY;
          return (
            <rect
              key={point.day}
              x={index * (4 + GAP)}
              y={y}
              width={4}
              height={barHeight}
              fill={value < 0 ? "#B91C1C" : "#15803D"}
              fillOpacity={0.85}
            >
              <title>{`${formatDayShort(point.day)}: ${formatMoney(point.profit)}`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="flex justify-between text-[11px] text-ink-faint">
        <span>{formatDayShort(points[0].day)}</span>
        <span>{formatDayShort(points[points.length - 1].day)}</span>
      </div>
    </div>
  );
}

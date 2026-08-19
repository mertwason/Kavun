/**
 * Kâr şelalesi — ürünün imza görseli (handoff `Siparis Detayi.dc.html`).
 *
 * Dikey kolon düzeni: 300px çizim alanı, eşit genişlikte kolonlar, barlar kolon içinde
 * %20–%80 aralığında. Her bar bir öncekinin bıraktığı yerden başlar; aralarındaki kesikli
 * bağlantı çizgisi komşu kolonlara %18 taşar. Bar üstünde tutar (kırmızı kesinti, yeşil
 * kâr), altında kolon etiketi; solda ₺ gutter'ı ve yatay kesikli gridline'lar.
 *
 * Ek bağımlılık yok — düz HTML/CSS. Kesinleşmemiş kalemin tutarı amber noktayla işaretli
 * (ürünün DNA'sı: kesin vs tahmini hücre seviyesinde görünür).
 */

import { EstimateDot } from "@/components/estimate-dot";
import type { WaterfallStep } from "@/lib/api";
import { formatMoney, formatMoneyWhole, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

const LABELS: Record<string, string> = tr.waterfall;

const PLOT_HEIGHT = 300;
const LABEL_ROOM = 24;
const GRID_LINES = 4;

/**
 * Bar rengi **işarete** göre seçilir, konuma göre değil: KDV adımı pozitif olabilir
 * (indirilecek KDV satış KDV'sini aşarsa) ve kârı ARTIRIR — onu kesinti kırmızısıyla
 * çizmek yanıltıcı olurdu.
 */
function barColor(bar: { amount: number }, isStart: boolean, isTotal: boolean): string {
  if (isStart) return "#E7E5E4";
  if (isTotal) return bar.amount < 0 ? "#DC2626" : "#16A34A";
  return bar.amount < 0 ? "rgba(220,38,38,0.8)" : "rgba(22,163,74,0.75)";
}

function labelColor(bar: { amount: number }, isStart: boolean, isTotal: boolean): string {
  if (isStart) return "#44403C";
  if (isTotal) return bar.amount < 0 ? "#DC2626" : "#15803D";
  return bar.amount < 0 ? "#DC2626" : "#15803D";
}

export function Waterfall({
  steps,
  estimatedKeys = [],
}: {
  steps: WaterfallStep[];
  /** Kesinleşmemiş adımlar — tutarlarının yanında amber nokta çıkar. */
  estimatedKeys?: string[];
}) {
  // Sıfır adımlar gizlenir (reklam payı Faz 4'e kadar sıfır) ama satış ve kâr her zaman
  // durur: şelalenin başı ve sonu görünmeli.
  const visible = steps.filter(
    (step) => toNumber(step.amount) !== 0 || step.key === "satis" || step.key === "kar",
  );
  if (visible.length === 0) return null;

  let running = 0;
  const bars = visible.map((step) => {
    const amount = toNumber(step.amount);
    const isTotal = step.key === "kar";
    const start = isTotal ? 0 : running;
    const end = isTotal ? amount : running + amount;
    if (!isTotal) running = end;
    return { key: step.key, amount, top: Math.min(start, end), bottom: Math.max(start, end) };
  });

  const peak = Math.max(...bars.map((bar) => bar.bottom), 0);
  const floor = Math.min(...bars.map((bar) => bar.top), 0);
  const span = peak - floor || 1;
  const toY = (value: number) => ((peak - value) / span) * PLOT_HEIGHT;

  const gridValues = Array.from({ length: GRID_LINES + 1 }, (_, index) =>
    floor + (span * index) / GRID_LINES,
  );

  return (
    <div className="flex gap-2">
      <div className="relative w-11 shrink-0" style={{ height: PLOT_HEIGHT + LABEL_ROOM }}>
        {gridValues.map((value) => (
          <span
            key={value}
            className="absolute right-0 -translate-y-1/2 text-micro text-ink-muted"
            style={{ top: LABEL_ROOM + toY(value) }}
          >
            {formatMoneyWhole(value)}
          </span>
        ))}
      </div>

      <div className="relative min-w-0 flex-1" style={{ height: PLOT_HEIGHT + LABEL_ROOM }}>
        {gridValues.map((value, index) => (
          <div
            key={value}
            className="absolute inset-x-0"
            style={{
              top: LABEL_ROOM + toY(value),
              borderTop: index === GRID_LINES ? "1px solid #E7E5E4" : "1px dashed #EBE9E7",
            }}
          />
        ))}

        <div
          className="absolute inset-x-0 grid"
          style={{
            top: LABEL_ROOM,
            height: PLOT_HEIGHT,
            gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))`,
          }}
        >
          {bars.map((bar, index) => {
            const top = toY(bar.bottom);
            const height = Math.max(2, toY(bar.top) - toY(bar.bottom));
            const isTotal = bar.key === "kar";
            const isStart = index === 0;
            const estimated = estimatedKeys.includes(bar.key);

            return (
              <div key={bar.key} className="relative">
                {/* Bir önceki barın bittiği yerden bu bara uzanan kesikli bağlantı. */}
                {isStart ? null : (
                  <div
                    className="absolute border-t border-dashed border-ink-ghost"
                    style={{ top: toY(isTotal ? 0 : bar.bottom), left: "-18%", width: "36%" }}
                  />
                )}

                <div
                  className="absolute inset-x-0 flex items-center justify-center gap-1.5 text-helper font-semibold"
                  style={{ top: Math.max(0, top - 22), color: labelColor(bar, isStart, isTotal) }}
                >
                  {estimated ? <EstimateDot /> : null}
                  {formatMoney(bar.amount)}
                </div>

                <div
                  title={`${LABELS[bar.key] ?? bar.key}: ${formatMoney(bar.amount)}`}
                  className="absolute rounded-[3px]"
                  style={{
                    top,
                    height,
                    left: "20%",
                    right: "20%",
                    background: barColor(bar, isStart, isTotal),
                    border: isStart ? "1px solid #D6D3D1" : undefined,
                  }}
                />
              </div>
            );
          })}
        </div>

        <div
          className="absolute inset-x-0 grid gap-1"
          style={{
            top: LABEL_ROOM + PLOT_HEIGHT + 8,
            gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))`,
          }}
        >
          {bars.map((bar) => (
            <span key={bar.key} className="truncate text-center text-helper text-ink-secondary">
              {LABELS[bar.key] ?? bar.key}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

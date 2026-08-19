/**
 * KPI kartı — handoff `Dashboard.dc.html`.
 *
 * Yapı: etiket (13px, `#78716C`) → büyük rakam (29px/600, `letter-spacing:-0.02em`;
 * ₺ simgesi bir kademe küçük ve soluk) → isteğe bağlı alt satır → delta + sparkline.
 *
 * Delta rengi **anlamla** belirlenir, yönle değil: iade oranındaki artış kötüdür, o yüzden
 * `higherIsBetter=false` geçilir ve artış kırmızı çizilir.
 */

import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { ReactNode } from "react";

import { Sparkline } from "@/components/sparkline";
import { formatMoneyParts, formatPercent, formatPoint, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

export type KpiFormat = "money" | "percent" | "text";

export function KpiCard({
  label,
  value,
  format = "text",
  hint,
  tone = "neutral",
  footer,
  delta,
  deltaKind = "percent",
  higherIsBetter = true,
  series,
  children,
}: {
  label: string;
  value: string | number;
  /**
   * `text` (varsayılan) değeri olduğu gibi yazar — henüz yeni tasarıma geçmemiş ekranlar
   * tutarı kendileri biçimlendirip geçiyor. `money` ham sayı alır ve ₺ simgesini
   * handoff'un istediği gibi küçük/soluk çizer.
   */
  format?: KpiFormat;
  hint?: string;
  tone?: "neutral" | "positive" | "negative";
  footer?: ReactNode;
  /** Önceki döneme göre değişim; veri yoksa satır çizilmez (uydurma delta yok). */
  delta?: number | null;
  /** Yüzde metrikleri puan farkı olarak yazılır: `−1,2 pt`. */
  deltaKind?: "percent" | "point";
  higherIsBetter?: boolean;
  series?: number[];
  children?: ReactNode;
}) {
  const positive = delta !== null && delta !== undefined && delta >= 0;
  const good = positive === higherIsBetter;
  const deltaColor = good ? "#16A34A" : "#DC2626";

  return (
    <div className="card p-[18px_20px]">
      <div className="text-cell text-ink-body">{label}</div>

      <div className="mt-2 flex items-baseline gap-[3px]" data-kpi-value>
        {format === "money" ? (
          <MoneyValue value={value} />
        ) : (
          <span className={`text-kpi ${toneClass(tone)}`}>
            {format === "percent" ? formatPercent(value) : String(value)}
          </span>
        )}
      </div>

      {hint ? <div className="mt-1 text-helper text-ink-muted">{hint}</div> : null}
      {children}
      {footer ? (
        <div className="mt-2 border-t border-hairline pt-2 text-helper">{footer}</div>
      ) : null}

      {delta === null || delta === undefined ? null : (
        <div className="mt-3 flex items-center justify-between">
          <span
            className="inline-flex items-center gap-1 text-helper font-medium"
            style={{ color: deltaColor }}
          >
            {positive ? (
              <ArrowUpRight className="h-3 w-3" aria-hidden />
            ) : (
              <ArrowDownRight className="h-3 w-3" aria-hidden />
            )}
            {deltaKind === "point" ? formatPoint(delta) : formatSignedPercent(delta)}
            <span className="font-normal text-ink-muted"> · {tr.kpi.deltaWindow}</span>
          </span>
          {series && series.length > 1 ? <Sparkline values={series} color={deltaColor} /> : null}
        </div>
      )}
    </div>
  );
}

/** ₺ simgesi rakamdan bir kademe küçük ve soluk (handoff, Tipografi). */
function MoneyValue({ value }: { value: string | number }) {
  const parts = formatMoneyParts(value, { whole: true });
  return (
    <>
      {parts.sign ? <span className="text-kpi">{parts.sign}</span> : null}
      <span className="text-kpiSm font-medium text-ink-muted">{parts.symbol}</span>
      <span className="text-kpi">{parts.digits}</span>
    </>
  );
}

function toneClass(tone: "neutral" | "positive" | "negative"): string {
  if (tone === "positive") return "text-positive-text";
  if (tone === "negative") return "text-negative";
  return "";
}

function formatSignedPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${formatPercent(value)}`;
}

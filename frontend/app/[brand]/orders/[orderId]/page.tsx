/**
 * Sipariş detayı — satır bazlı waterfall kâr dökümü (spec §10.3).
 *
 * Ürünün imza ekranı (tasarım brief'i, kalıp 4): satış fiyatından net kâra inen
 * şelale, önce sipariş toplamı sonra her satır için.
 */

import { EstimateDot } from "@/components/estimate-dot";
import { type SourceKind, SourceBadge } from "@/components/source-badge";
import { Waterfall } from "@/components/waterfall";
import {
  Card,
  EmptyState,
  ErrorState,
  EstimateBadge,
  SectionHeader,
  TextLink,
} from "@/components/ui";
import { fetchOrderDetail } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import {
  formatCount,
  formatDateTime,
  formatMoney,
  formatPercent,
  signClass,
  toNumber,
} from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const STATUS_LABELS: Record<string, string> = tr.status;
const COMMISSION_LABELS: Record<string, string> = tr.commissionSource;
const WATERFALL_LABELS: Record<string, string> = tr.waterfall;

/** Şelale adımının kaynağı — hangi rozet çizilecek (handoff, Kalem Dökümü). */
function sourceFor(key: string, order: { is_final: boolean }): SourceKind {
  if (key === "kargo") return order.is_final ? "kargoFatura" : "desi";
  if (key === "kdv") return "hesaplanan";
  if (key === "maliyet") return "fatura";
  if (key === "hizmet_bedeli") return "tarife";
  if (key === "komisyon") return "tarife";
  return "api";
}

export default async function OrderDetailPage({
  params,
}: {
  params: { brand: BrandSlug; orderId: string };
}) {
  const result = await fetchOrderDetail(params.brand, params.orderId);

  if (!result.ok) {
    return (
      <>
        <TextLink href={`/${params.brand}/orders`}>← {tr.detail.backToOrders}</TextLink>
        <Card>
          <ErrorState status={result.status} />
        </Card>
      </>
    );
  }

  const order = result.data;

  return (
    <>
      <TextLink href={`/${params.brand}/orders`}>← {tr.detail.backToOrders}</TextLink>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="col-head">
            {tr.detail.orderTitle}
          </span>
          <h1 className="font-mono text-title font-medium">{order.external_order_id}</h1>
          <p className="text-helper text-ink-muted">
            {formatDateTime(order.order_date)} · {order.store_name} ·{" "}
            {STATUS_LABELS[order.status] ?? order.status}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="text-helper text-ink-muted">{tr.detail.netProfit}</span>
          <span className={`text-kpi ${signClass(order.profit)}`}>
            {formatMoney(order.profit)}
          </span>
          <div className="flex items-center gap-3 text-helper">
            <span className={signClass(order.margin_pct)}>{formatPercent(order.margin_pct)}</span>
            <EstimateBadge isFinal={order.is_final} />
          </div>
        </div>
      </div>

      {order.lines.length === 0 ? (
        <Card>
          <EmptyState title={tr.empty.orderLines} />
        </Card>
      ) : (
        <>
          <Card className="flex flex-col gap-4 p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <SectionHeader
                title={tr.chart.waterfallTitle}
                subtitle={tr.chart.waterfallSubtitle}
              />
              <span
                className={`flex items-center gap-1.5 text-helper ${
                  order.is_final ? "text-positive-text" : "text-estimated-text"
                }`}
              >
                {order.is_final ? null : <EstimateDot />}
                {order.is_final
                  ? tr.detail.allFinal
                  : tr.detail.estimatedNote.replace("{count}", "1")}
              </span>
            </div>
            <Waterfall
              steps={order.waterfall}
              estimatedKeys={order.is_final ? [] : ["kargo"]}
            />
          </Card>

          <Card className="flex flex-col">
            <div className="p-5 pb-2">
              <SectionHeader title={tr.detail.breakdownTitle} />
            </div>
            <table className="w-full border-collapse text-cell">
              <thead>
                <tr className="border-b border-hairline">
                  <th className="px-5 py-2 text-left">
                    <span className="col-head">{tr.detail.item}</span>
                  </th>
                  <th className="px-5 py-2 text-left">
                    <span className="col-head">{tr.detail.source}</span>
                  </th>
                  <th className="px-5 py-2 text-right">
                    <span className="col-head">{tr.detail.amount}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {order.waterfall
                  .filter((step) => step.key !== "kar" && toNumber(step.amount) !== 0)
                  .map((step) => (
                    <tr key={step.key} className="border-b border-divider">
                      <td className="px-5 py-[11px]">{WATERFALL_LABELS[step.key] ?? step.key}</td>
                      <td className="px-5 py-[11px]">
                        <SourceBadge kind={sourceFor(step.key, order)} />
                      </td>
                      <td className="px-5 py-[11px] text-right font-medium">
                        {formatMoney(step.amount)}
                      </td>
                    </tr>
                  ))}
                <tr className="bg-canvas">
                  <td className="px-5 py-[11px] font-medium">{tr.detail.netProfit}</td>
                  <td className="px-5 py-[11px]">
                    <span className="badge border-positive-border bg-positive-tint text-positive-text">
                      {tr.table.margin} {formatPercent(order.margin_pct)}
                    </span>
                  </td>
                  <td className="px-5 py-[11px] text-right">
                    <span className="inline-flex items-center gap-1.5 font-semibold text-positive-text">
                      {order.is_final ? null : <EstimateDot />}
                      {formatMoney(order.profit)}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </Card>

          <div className="flex flex-col gap-4">
            <SectionHeader title={tr.detail.lineTitle} />
            {order.lines.map((line) => (
              <Card key={line.order_line_id} className="grid gap-6 p-5 lg:grid-cols-[1fr_1.4fr]">
                <div className="flex flex-col gap-3">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-mono text-helper text-ink-muted">{line.sku ?? "—"}</span>
                    <span className="text-cell font-medium">{line.name ?? tr.table.line}</span>
                  </div>
                  <dl className="flex flex-col gap-1.5 text-helper">
                    <Row label={tr.table.qty} value={formatCount(line.qty)} />
                    <Row label={tr.table.total} value={formatMoney(line.line_gross)} />
                    <Row label={tr.table.vat} value={formatPercent(line.vat_rate)} />
                    <Row
                      label={tr.detail.commission}
                      value={
                        line.commission_source
                          ? (COMMISSION_LABELS[line.commission_source] ?? line.commission_source)
                          : COMMISSION_LABELS.unknown
                      }
                    />
                    <Row
                      label={tr.table.margin}
                      value={formatPercent(line.margin_pct)}
                      className={signClass(line.margin_pct)}
                    />
                  </dl>
                  <EstimateBadge isFinal={line.is_final} />
                </div>
                <Waterfall steps={line.waterfall} />
              </Card>
            ))}
          </div>
        </>
      )}
    </>
  );
}

function Row({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-hairline pb-1.5">
      <dt className="col-head">{label}</dt>
      <dd className={`tabular ${className}`}>{value}</dd>
    </div>
  );
}

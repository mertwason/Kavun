/**
 * Sipariş detayı — satır bazlı waterfall kâr dökümü (spec §10.3).
 *
 * Ürünün imza ekranı (tasarım brief'i, kalıp 4): satış fiyatından net kâra inen
 * şelale, önce sipariş toplamı sonra her satır için.
 */

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
import { formatCount, formatDateTime, formatMoney, formatPercent, signClass } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const STATUS_LABELS: Record<string, string> = tr.status;
const COMMISSION_LABELS: Record<string, string> = tr.commissionSource;

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
          <span className="text-xs uppercase tracking-wide text-ink-faint">
            {tr.detail.orderTitle}
          </span>
          <h1 className="font-mono text-lg font-medium">{order.external_order_id}</h1>
          <p className="text-xs text-ink-faint">
            {formatDateTime(order.order_date)} · {order.store_name} ·{" "}
            {STATUS_LABELS[order.status] ?? order.status}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="text-xs text-ink-faint">{tr.detail.netProfit}</span>
          <span className={`tabular text-2xl font-medium ${signClass(order.profit)}`}>
            {formatMoney(order.profit)}
          </span>
          <div className="flex items-center gap-3 text-xs">
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
            <SectionHeader title={tr.chart.waterfallTitle} subtitle={tr.chart.waterfallSubtitle} />
            <Waterfall steps={order.waterfall} />
            {!order.is_final ? (
              <p className="text-xs text-estimated">{tr.estimate.explain}</p>
            ) : null}
          </Card>

          <div className="flex flex-col gap-4">
            <SectionHeader title={tr.detail.lineTitle} />
            {order.lines.map((line) => (
              <Card key={line.order_line_id} className="grid gap-6 p-5 lg:grid-cols-[1fr_1.4fr]">
                <div className="flex flex-col gap-3">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-mono text-xs text-ink-faint">{line.sku ?? "—"}</span>
                    <span className="text-sm font-medium">{line.name ?? tr.table.line}</span>
                  </div>
                  <dl className="flex flex-col gap-1.5 text-xs">
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
      <dt className="text-ink-faint">{label}</dt>
      <dd className={`tabular ${className}`}>{value}</dd>
    </div>
  );
}

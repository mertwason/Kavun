/** Sipariş listesi — kâr dökümü ekranının giriş kapısı (spec §10.3). */

import Link from "next/link";

import { DEFAULT_DAYS, PeriodPicker, periodRange, resolveDays } from "@/components/period-picker";
import {
  Card,
  DataTable,
  EmptyState,
  ErrorState,
  EstimateBadge,
  Td,
  Th,
  Tr,
} from "@/components/ui";
import { fetchOrders } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatDateTime, formatMoney, formatPercent, signClass, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const STATUS_LABELS: Record<string, string> = tr.status;

export default async function OrdersPage({
  params,
  searchParams,
}: {
  params: { brand: BrandSlug };
  searchParams: { days?: string };
}) {
  const days = resolveDays(searchParams.days ?? String(DEFAULT_DAYS));
  const result = await fetchOrders(params.brand, periodRange(days));

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-medium">{tr.nav.orders}</h1>
        <PeriodPicker basePath={`/${params.brand}/orders`} activeDays={days} />
      </div>

      <Card>
        {!result.ok ? (
          <ErrorState status={result.status} />
        ) : result.data.length === 0 ? (
          <EmptyState title={tr.empty.orders} hint={tr.empty.ordersHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.table.order}</Th>
                <Th>{tr.table.date}</Th>
                <Th>{tr.table.store}</Th>
                <Th>{tr.table.status}</Th>
                <Th align="right">{tr.table.total}</Th>
                <Th align="right">{tr.table.profit}</Th>
                <Th align="right">{tr.table.margin}</Th>
                <Th>{tr.table.state}</Th>
              </>
            }
          >
            {result.data.map((row) => (
              <Tr key={row.order_id} negative={toNumber(row.profit) < 0}>
                <Td>
                  <Link
                    href={`/${params.brand}/orders/${row.order_id}`}
                    className="font-mono text-xs underline underline-offset-4 hover:text-ink"
                  >
                    {row.external_order_id}
                  </Link>
                </Td>
                <Td className="text-ink-muted">{formatDateTime(row.order_date)}</Td>
                <Td className="text-ink-muted">{row.store_name}</Td>
                <Td className="text-ink-muted">{STATUS_LABELS[row.status] ?? row.status}</Td>
                <Td align="right">{formatMoney(row.gross_total)}</Td>
                <Td align="right" className={signClass(row.profit)}>
                  {formatMoney(row.profit)}
                </Td>
                <Td align="right" className={signClass(row.margin_pct)}>
                  {formatPercent(row.margin_pct)}
                </Td>
                <Td>
                  <EstimateBadge isFinal={row.is_final} />
                </Td>
              </Tr>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  );
}

/** SKU marj listesi — negatif marj kırmızı, en düşük kâr üstte (spec §10.2). */

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
import { fetchSkuMargins } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatCount, formatMoney, formatPercent, signClass, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function SkuMarginsPage({
  params,
  searchParams,
}: {
  params: { brand: BrandSlug };
  searchParams: { days?: string; negative?: string };
}) {
  const days = resolveDays(searchParams.days ?? String(DEFAULT_DAYS));
  const onlyNegative = searchParams.negative === "1";
  const result = await fetchSkuMargins(params.brand, periodRange(days));
  const rows = result.ok
    ? result.data.filter((row) => !onlyNegative || toNumber(row.profit) < 0)
    : [];
  const basePath = `/${params.brand}/sku`;

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-medium">{tr.nav.skuMargins}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1 text-xs">
            <Link
              href={`${basePath}?days=${days}`}
              aria-current={onlyNegative ? undefined : "page"}
              className={
                onlyNegative
                  ? "rounded-full px-2.5 py-1 text-ink-faint hover:text-ink"
                  : "rounded-full border border-hairline bg-surface px-2.5 py-1 font-medium text-ink"
              }
            >
              {tr.table.allRows}
            </Link>
            <Link
              href={`${basePath}?days=${days}&negative=1`}
              aria-current={onlyNegative ? "page" : undefined}
              className={
                onlyNegative
                  ? "rounded-full border border-hairline bg-surface px-2.5 py-1 font-medium text-ink"
                  : "rounded-full px-2.5 py-1 text-ink-faint hover:text-ink"
              }
            >
              {tr.table.onlyNegative}
            </Link>
          </div>
          <PeriodPicker basePath={basePath} activeDays={days} />
        </div>
      </div>

      <Card>
        {!result.ok ? (
          <ErrorState status={result.status} />
        ) : rows.length === 0 ? (
          <EmptyState title={tr.empty.sku} hint={tr.empty.skuHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.table.sku}</Th>
                <Th>{tr.table.product}</Th>
                <Th>{tr.table.category}</Th>
                <Th align="right">{tr.table.qty}</Th>
                <Th align="right">{tr.table.revenue}</Th>
                <Th align="right">{tr.table.cost}</Th>
                <Th align="right">{tr.table.profit}</Th>
                <Th align="right">{tr.table.margin}</Th>
                <Th>{tr.table.state}</Th>
              </>
            }
          >
            {rows.map((row) => (
              <Tr key={row.product_id} negative={toNumber(row.profit) < 0}>
                <Td className="font-mono text-xs text-ink-muted">{row.sku}</Td>
                <Td>{row.name}</Td>
                <Td className="text-ink-muted">{row.category ?? "—"}</Td>
                <Td align="right">{formatCount(row.qty_sold)}</Td>
                <Td align="right">{formatMoney(row.revenue_gross)}</Td>
                <Td align="right">{formatMoney(row.cost_cogs)}</Td>
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

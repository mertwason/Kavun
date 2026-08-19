/**
 * Holding görünümü — markalar arası konsolide rapor (spec §3A.3).
 *
 * Salt okunur: burada hiçbir işlem yapılamaz, hiçbir form yoktur. Yetkisiz kullanıcıda
 * API 403 döner ve ekran bunu açık bir mesajla gösterir.
 */

import Link from "next/link";

import { KpiCard } from "@/components/kpi-card";
import { Card, DataTable, EmptyState, SectionHeader, Td, Th, Tr } from "@/components/ui";
import { fetchConsolidated } from "@/lib/api";
import { BRANDS, isBrandSlug } from "@/lib/brands";
import { formatAmount, formatDate, formatMoney, formatPercent, signClass } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function HoldingPage() {
  const report = await fetchConsolidated();

  if (!report.ok) {
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-20">
        <h1 className="text-lg font-medium">{tr.holding.title}</h1>
        <Card>
          <EmptyState title={tr.holding.denied} hint={tr.holding.deniedHint} />
        </Card>
        <Link href="/" className="text-sm text-ink-muted underline underline-offset-4">
          {tr.holding.backHome}
        </Link>
      </main>
    );
  }

  const data = report.data;

  return (
    <main className="mx-auto flex max-w-[1440px] flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-medium">{tr.holding.title}</h1>
          <p className="text-xs text-ink-faint">{tr.holding.subtitle}</p>
        </div>
        <span className="text-xs text-ink-faint">
          {formatDate(data.since)} — {formatDate(data.until)}
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <KpiCard label={tr.holding.totalRevenue} value={formatMoney(data.total_revenue)} />
        <KpiCard
          label={tr.holding.totalProfit}
          value={formatMoney(data.total_profit)}
          tone={Number(data.total_profit) < 0 ? "negative" : "neutral"}
        />
        <KpiCard label={tr.holding.totalStock} value={formatMoney(data.total_stock_value)} />
        <KpiCard
          label={tr.holding.damage}
          value={formatMoney(data.total_damage_cost)}
          tone={Number(data.total_damage_cost) > 0 ? "negative" : "neutral"}
        />
      </div>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.holding.breakdown} />
        </div>
        <DataTable
          head={
            <>
              <Th>{tr.holding.brand}</Th>
              <Th align="right">{tr.holding.orders}</Th>
              <Th align="right">{tr.holding.revenue}</Th>
              <Th align="right">{tr.holding.profit}</Th>
              <Th align="right">{tr.holding.margin}</Th>
              <Th align="right">{tr.holding.stockValue}</Th>
              <Th align="right">{tr.holding.damage}</Th>
              <Th align="right">{tr.holding.fxDiff}</Th>
              <Th align="right">{tr.holding.openFx}</Th>
              <Th align="right">{tr.holding.alerts}</Th>
            </>
          }
        >
          {data.brands.map((row) => (
            <Tr key={row.brand}>
              <Td>
                {isBrandSlug(row.brand) ? (
                  <Link href={`/${row.brand}`} className="underline underline-offset-4">
                    {BRANDS[row.brand].name}
                  </Link>
                ) : (
                  row.name
                )}
              </Td>
              <Td align="right">{row.order_count}</Td>
              <Td align="right">{formatMoney(row.revenue)}</Td>
              <Td align="right" className={signClass(row.profit)}>
                {formatMoney(row.profit)}
              </Td>
              <Td align="right" className={signClass(row.margin_pct)}>
                {formatPercent(row.margin_pct)}
              </Td>
              <Td align="right">{formatMoney(row.stock_value)}</Td>
              <Td align="right" className={Number(row.damage_cost) > 0 ? "text-negative" : ""}>
                {formatMoney(row.damage_cost)}
              </Td>
              <Td align="right" className={signClass(row.fx_diff)}>
                {formatMoney(row.fx_diff)}
              </Td>
              <Td align="right">{formatAmount(row.open_fx_amount)}</Td>
              <Td align="right">{row.open_alert_count}</Td>
            </Tr>
          ))}
        </DataTable>
      </Card>

      <Link href="/" className="text-sm text-ink-muted underline underline-offset-4">
        {tr.holding.backHome}
      </Link>
    </main>
  );
}

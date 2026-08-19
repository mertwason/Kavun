/** Dashboard — dönem KPI'ları, günlük kâr grafiği, mağaza kırılımı (spec §10.1). */

import { DailyProfitChart } from "@/components/daily-chart";
import { KpiCard } from "@/components/kpi-card";
import { DEFAULT_DAYS, PeriodPicker, periodRange, resolveDays } from "@/components/period-picker";
import { Card, DataTable, EmptyState, ErrorState, SectionHeader, Td, Th, Tr } from "@/components/ui";
import { type Dashboard, fetchDashboard } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatCount, formatMoney, formatPercent, signClass, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function DashboardPage({
  params,
  searchParams,
}: {
  params: { brand: BrandSlug };
  searchParams: { days?: string };
}) {
  const days = resolveDays(searchParams.days ?? String(DEFAULT_DAYS));
  const result = await fetchDashboard(params.brand, periodRange(days));

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-medium">{tr.nav.dashboard}</h1>
        <PeriodPicker basePath={`/${params.brand}`} activeDays={days} />
      </div>

      {!result.ok ? (
        <Card>
          <ErrorState status={result.status} />
        </Card>
      ) : result.data.kpis.line_count === 0 ? (
        <Card>
          <EmptyState title={tr.empty.dashboard} hint={tr.empty.dashboardHint} />
        </Card>
      ) : (
        <DashboardBody data={result.data} />
      )}
    </>
  );
}

function DashboardBody({ data }: { data: Dashboard }) {
  const { kpis } = data;
  const profitValue = toNumber(kpis.profit);

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label={tr.kpi.revenue}
          value={formatMoney(kpis.revenue_gross)}
          hint={tr.kpi.revenueHint}
          footer={
            <span className="text-ink-faint">
              {formatCount(kpis.order_count)} {tr.kpi.orders} · {formatCount(kpis.line_count)}{" "}
              {tr.kpi.lines}
            </span>
          }
        />
        <KpiCard
          label={tr.kpi.profit}
          value={formatMoney(kpis.profit)}
          hint={tr.kpi.profitHint}
          tone={profitValue < 0 ? "negative" : "positive"}
          footer={
            <div className="flex flex-col gap-0.5">
              <span className="text-estimated">
                {tr.estimate.estimatedProfit}: {formatMoney(kpis.estimated_profit)}
              </span>
              <span className="text-ink-faint">
                {tr.estimate.finalProfit}: {formatMoney(kpis.final_profit)}
              </span>
            </div>
          }
        />
        <KpiCard
          label={tr.kpi.margin}
          value={formatPercent(kpis.margin_pct)}
          hint={tr.kpi.marginHint}
          tone={toNumber(kpis.margin_pct) < 0 ? "negative" : "neutral"}
        />
        <KpiCard
          label={tr.kpi.returnRate}
          value={formatPercent(kpis.return_rate_pct)}
          hint={tr.kpi.returnRateHint}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[3fr_2fr]">
        <Card className="flex flex-col gap-4 p-5">
          <SectionHeader title={tr.chart.dailyTitle} subtitle={tr.chart.dailySubtitle} />
          <DailyProfitChart points={data.daily} />
        </Card>

        <Card className="flex flex-col">
          <div className="p-5 pb-3">
            <SectionHeader title={tr.chart.storesTitle} />
          </div>
          <DataTable
            head={
              <>
                <Th>{tr.table.store}</Th>
                <Th align="right">{tr.table.revenue}</Th>
                <Th align="right">{tr.table.profit}</Th>
                <Th align="right">{tr.table.margin}</Th>
              </>
            }
          >
            {data.stores.map((store) => (
              <Tr key={store.store_id} negative={toNumber(store.profit) < 0}>
                <Td>{store.store_name}</Td>
                <Td align="right">{formatMoney(store.revenue_gross)}</Td>
                <Td align="right" className={signClass(store.profit)}>
                  {formatMoney(store.profit)}
                </Td>
                <Td align="right" className={signClass(store.margin_pct)}>
                  {formatPercent(store.margin_pct)}
                </Td>
              </Tr>
            ))}
          </DataTable>
        </Card>
      </div>
    </>
  );
}

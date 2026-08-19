/**
 * Dashboard — handoff `Dashboard.dc.html` (spec §10.1).
 *
 * Dört KPI kartı (delta + sparkline), günlük net kâr alan grafiği (kesin/tahmini bantlı),
 * yanında "Bugün" ve "Son Uyarılar", altta kanal kırılımı ve SKU kâr uçları.
 *
 * **Delta uydurulmaz:** önceki eşit uzunlukta dönem ayrıca çekilir ve karşılaştırma ondan
 * hesaplanır; önceki dönemde veri yoksa delta satırı hiç çizilmez.
 */

import Link from "next/link";

import { AlertDot } from "@/components/alert-dot";
import { BarList } from "@/components/bar-list";
import { DailyProfitChart } from "@/components/daily-chart";
import { EstimateDot } from "@/components/estimate-dot";
import { KpiCard } from "@/components/kpi-card";
import { DEFAULT_DAYS, PeriodPicker, periodRange, resolveDays } from "@/components/period-picker";
import { Card, EmptyState, ErrorState, SectionHeader } from "@/components/ui";
import {
  type AlertRow,
  type Dashboard,
  fetchAlerts,
  fetchDashboard,
  fetchSkuMargins,
  type SkuMargin,
} from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import {
  formatCount,
  formatDate,
  formatMoney,
  formatMoneyWhole,
  formatPercent,
  formatRelativeTime,
  toNumber,
} from "@/lib/format";
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
  const current = periodRange(days);
  const previous = shiftBack(current, days);

  const [result, previousResult, skus, alerts] = await Promise.all([
    fetchDashboard(params.brand, current),
    fetchDashboard(params.brand, previous),
    fetchSkuMargins(params.brand, current),
    fetchAlerts(params.brand, { acknowledged: false }),
  ]);

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="sr-only">{tr.nav.dashboard}</h1>
        <span />
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
        <DashboardBody
          brand={params.brand}
          data={result.data}
          previous={previousResult.ok ? previousResult.data : null}
          skus={skus.ok ? skus.data : []}
          alerts={alerts.ok ? alerts.data.slice(0, 5) : []}
        />
      )}
    </>
  );
}

function DashboardBody({
  brand,
  data,
  previous,
  skus,
  alerts,
}: {
  brand: BrandSlug;
  data: Dashboard;
  previous: Dashboard | null;
  skus: SkuMargin[];
  alerts: AlertRow[];
}) {
  const { kpis, daily, stores } = data;
  const previousKpis = previous?.kpis ?? null;

  const revenueSeries = daily.map((point) => toNumber(point.revenue_gross));
  const profitSeries = daily.map((point) => toNumber(point.profit));
  // Günlük marj serisi: ciro sıfır olan günde marj tanımsızdır, o gün atlanır.
  const marginSeries = daily
    .filter((point) => toNumber(point.revenue_gross) !== 0)
    .map((point) => (toNumber(point.profit) / toNumber(point.revenue_gross)) * 100);
  const today = daily.at(-1);

  const sorted = [...skus].sort((a, b) => toNumber(b.profit) - toNumber(a.profit));
  const best = sorted.slice(0, 5);
  const worst = sorted
    .filter((row) => toNumber(row.profit) < 0)
    .slice(-5)
    .reverse();

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label={tr.kpi.revenue}
          value={kpis.revenue_gross}
          format="money"
          delta={growth(kpis.revenue_gross, previousKpis?.revenue_gross)}
          series={revenueSeries}
        />

        <KpiCard
          label={tr.kpi.profit}
          value={kpis.profit}
          format="money"
          delta={growth(kpis.profit, previousKpis?.profit)}
          series={profitSeries}
        >
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11.5px] text-ink-body">
            <span>
              {formatMoneyWhole(kpis.final_profit)} {tr.kpi.finalShort}
            </span>
            <span className="text-ink-ghost">·</span>
            <EstimateDot />
            <span className="text-estimated-text">
              {formatMoneyWhole(kpis.estimated_profit)} {tr.kpi.estimatedShort}
            </span>
          </div>
        </KpiCard>

        <KpiCard
          label={tr.kpi.margin}
          value={kpis.margin_pct}
          format="percent"
          delta={difference(kpis.margin_pct, previousKpis?.margin_pct)}
          deltaKind="point"
          series={marginSeries}
        />

        <KpiCard
          label={tr.kpi.returnRate}
          value={kpis.return_rate_pct}
          format="percent"
          delta={difference(kpis.return_rate_pct, previousKpis?.return_rate_pct)}
          deltaKind="point"
          // İade oranındaki ARTIŞ kötüdür: renk yönü tersine çevrilir.
          higherIsBetter={false}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card className="flex flex-col gap-3 p-5">
          <SectionHeader title={tr.dashboard.dailyTitle} />
          <DailyProfitChart points={daily} />
        </Card>

        <div className="flex flex-col gap-4">
          <Card className="flex flex-col gap-2 p-5">
            <SectionHeader
              title={tr.dashboard.todayTitle}
              subtitle={today ? formatDate(today.day) : undefined}
            />
            <TodayRow
              label={tr.dashboard.todayOrders}
              value={formatCount(today?.order_count ?? 0)}
            />
            <TodayRow
              label={tr.dashboard.todayRevenue}
              value={formatMoney(today?.revenue_gross ?? 0)}
            />
            <TodayRow
              label={tr.dashboard.todayProfit}
              value={formatMoney(today?.profit ?? 0)}
              estimated={toNumber(today?.profit) !== toNumber(today?.final_profit)}
            />
          </Card>

          <Card className="flex flex-col gap-2 p-5">
            <div className="flex items-baseline justify-between">
              <SectionHeader title={tr.dashboard.recentAlerts} />
              <Link href={`/${brand}/alerts`} className="text-helper text-ink-muted hover:text-ink">
                {tr.dashboard.all}
              </Link>
            </div>
            {alerts.length === 0 ? (
              <p className="text-cell text-ink-muted">{tr.empty.alerts}</p>
            ) : (
              alerts.map((alert) => (
                <div key={alert.id} className="flex items-center gap-2 py-[3px]">
                  <AlertDot severity={alert.severity} />
                  <span className="min-w-0 flex-1 truncate text-cell">{alert.message}</span>
                  <span className="shrink-0 text-micro text-ink-muted">
                    {formatRelativeTime(alert.created_at)}
                  </span>
                </div>
              ))
            )}
          </Card>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="flex flex-col gap-3 p-5">
          <SectionHeader title={tr.dashboard.channelTitle} />
          <BarList
            rows={stores.map((store) => ({
              key: store.store_id,
              initial: store.channel.slice(0, 1).toLocaleUpperCase("tr-TR"),
              label: store.store_name,
              value: toNumber(store.revenue_gross),
              display: formatMoneyWhole(store.revenue_gross),
            }))}
          />
        </Card>

        <Card className="flex flex-col p-5">
          <SectionHeader title={tr.dashboard.skuEdgesTitle} />
          <div className="mt-3 grid gap-5 sm:grid-cols-2 sm:divide-x sm:divide-hairline">
            <SkuColumn title={tr.dashboard.topSku} rows={best} tone="positive" />
            <SkuColumn title={tr.dashboard.bottomSku} rows={worst} tone="negative" className="sm:pl-5" />
          </div>
        </Card>
      </div>
    </>
  );
}

function TodayRow({
  label,
  value,
  estimated,
}: {
  label: string;
  value: string;
  estimated?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between text-cell">
      <span className="text-ink-body">{label}</span>
      <span className="flex items-center gap-1.5 font-medium">
        {estimated ? <EstimateDot /> : null}
        {value}
      </span>
    </div>
  );
}

function SkuColumn({
  title,
  rows,
  tone,
  className,
}: {
  title: string;
  rows: SkuMargin[];
  tone: "positive" | "negative";
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="col-head pb-1">{title}</div>
      {rows.length === 0 ? (
        <p className="py-1 text-cell text-ink-muted">—</p>
      ) : (
        rows.map((row) => (
          <div key={row.product_id} className="flex items-baseline gap-2 py-[5px]">
            <span className="w-[72px] shrink-0 truncate font-mono text-micro text-ink-muted">
              {row.sku}
            </span>
            <span className="min-w-0 flex-1 truncate text-cell">{row.name}</span>
            <span
              className={`text-cell font-medium ${
                tone === "positive" ? "text-positive" : "text-negative"
              }`}
            >
              {formatMoneyWhole(row.profit)}
            </span>
          </div>
        ))
      )}
    </div>
  );
}

/** Yüzdesel büyüme; önceki dönem yoksa ya da sıfırsa delta gösterilmez. */
function growth(current: string, previous: string | undefined): number | null {
  if (previous === undefined) return null;
  const before = toNumber(previous);
  if (before === 0) return null;
  return ((toNumber(current) - before) / Math.abs(before)) * 100;
}

/** Puan farkı (yüzde metrikleri için). */
function difference(current: string, previous: string | undefined): number | null {
  if (previous === undefined) return null;
  return toNumber(current) - toNumber(previous);
}

/** Karşılaştırma dönemi: aynı uzunlukta, hemen öncesi. */
function shiftBack(range: { from: string; to: string }, days: number) {
  const from = new Date(range.from);
  const to = new Date(range.to);
  from.setDate(from.getDate() - days);
  to.setDate(to.getDate() - days);
  return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
}

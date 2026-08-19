/**
 * Hakediş mutabakatı — handoff `Mutabakat.dc.html` (spec §7.4).
 *
 * Tek soru: platformun kestiği tutar bizim hesabımızla aynı mı? Üst şerit dönemin
 * eşleşme oranını ve açık fark tutarını verir; altta farklar **künyesiyle** (hangi kalem,
 * hangi sipariş) listelenir ve açıklama akışı buradan yürür.
 *
 * Handoff'ta "Eşleşmeyen Kayıtlar" adında üçüncü bir sekme var; Kavun eşleşmeyen kalemleri
 * kalıcı olarak saklamıyor (tur çıktısında geçici olarak raporlanıyor), bu yüzden o sekme
 * yerine turun sonucundaki eşleşmeyen referanslar panelde gösteriliyor. Kalıcı kuyruk
 * gerekirse önce veri modeline girmeli — boş bir sekme koymak yanıltıcı olurdu.
 */

import Link from "next/link";

import { DiffRow, ReconciliationRunner } from "@/components/reconciliation-panel";
import { Card, EmptyState, SectionHeader } from "@/components/ui";
import {
  fetchReconciliationDiffs,
  fetchReconciliationPeriods,
  fetchReconciliationSummary,
} from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatCount, formatMoney, formatMoneyParts, formatPercent } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

type Search = { period?: string; tab?: string };

const TABS = ["open", "closed", "all"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
  open: tr.reconciliation.tabOpen,
  closed: tr.reconciliation.tabClosed,
  all: tr.reconciliation.tabAll,
};

export default async function ReconciliationPage({
  params,
  searchParams,
}: {
  params: { brand: BrandSlug };
  searchParams: Search;
}) {
  const periodList = await fetchReconciliationPeriods(params.brand);
  const periods = periodList.ok ? periodList.data : [];
  const period = searchParams.period ?? periods[0] ?? "";
  const tab: Tab = TABS.includes(searchParams.tab as Tab) ? (searchParams.tab as Tab) : "open";

  const [diffs, summary] = await Promise.all([
    fetchReconciliationDiffs(params.brand, period || undefined),
    period
      ? fetchReconciliationSummary(params.brand, period)
      : Promise.resolve({ ok: false as const, status: 404, reason: "no-period" }),
  ]);

  const all = diffs.ok ? diffs.data : [];
  const rows = all.filter((diff) =>
    tab === "all" ? true : tab === "open" ? diff.status === "open" : diff.status !== "open",
  );
  const totals = summary.ok ? summary.data : null;
  const volume = formatMoneyParts(totals?.settlement_total ?? 0, { whole: true });

  const href = (next: Search) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...searchParams, ...next })) {
      if (value) query.set(key, String(value));
    }
    return `/${params.brand}/reconciliation${query.toString() ? `?${query}` : ""}`;
  };

  return (
    <>
      <h1 className="sr-only">{tr.reconciliation.title}</h1>

      {/* Üst şerit: dönemin tek bakışta durumu (handoff exec strip). */}
      <Card className="flex flex-wrap items-center gap-x-10 gap-y-5 rounded-exec p-5">
        <div className="flex flex-col gap-1">
          <span className="col-head">{period || tr.reconciliation.period}</span>
          <span className="text-kpi">
            {totals ? formatPercent(totals.match_rate_pct) : "—"}
          </span>
          <span className="text-helper text-ink-body">
            {totals
              ? `${volume.symbol}${volume.digits} ${tr.reconciliation.volume.toLocaleLowerCase("tr-TR")}`
              : tr.reconciliation.noPeriod}
          </span>
        </div>

        <Metric
          label={tr.reconciliation.openDiff}
          value={formatMoney(totals?.open_diff ?? 0)}
          tone={totals && totals.open_count > 0 ? "text-negative" : undefined}
        />
        <Metric
          label={tr.reconciliation.records}
          value={
            totals ? `${formatCount(totals.matched_count)} / ${formatCount(totals.record_count)}` : "—"
          }
        />
        <Metric
          label={tr.reconciliation.resolvedThisPeriod}
          value={formatCount((totals?.explained_count ?? 0) + (totals?.resolved_count ?? 0))}
        />

        {periods.length > 1 ? (
          <div className="flex flex-wrap items-center gap-1.5">
            {periods.slice(0, 6).map((item) => (
              <Link
                key={item}
                href={href({ period: item })}
                aria-current={item === period ? "true" : undefined}
                className={`flex h-7 items-center rounded-pill border px-2.5 text-helper ${
                  item === period
                    ? "border-ink bg-ink font-medium text-white"
                    : "border-hairline bg-surface text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
                }`}
              >
                {item}
              </Link>
            ))}
          </div>
        ) : null}
      </Card>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.reconciliation.run} subtitle={tr.reconciliation.diffsSubtitle} />
        <ReconciliationRunner brand={params.brand} periods={periods} />
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((item) => (
          <Link
            key={item}
            href={href({ tab: item })}
            aria-current={item === tab ? "true" : undefined}
            className={`flex h-7 items-center gap-1.5 rounded-pill border px-2.5 text-helper ${
              item === tab
                ? "border-ink bg-ink font-medium text-white"
                : "border-hairline bg-surface text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
            }`}
          >
            {TAB_LABELS[item]}
            <span className={item === tab ? "text-white/70" : "text-ink-muted"}>
              ·{" "}
              {formatCount(
                item === "all"
                  ? all.length
                  : all.filter((diff) =>
                      item === "open" ? diff.status === "open" : diff.status !== "open",
                    ).length,
              )}
            </span>
          </Link>
        ))}
        <span className="text-helper text-ink-muted">· {tr.reconciliation.diffHint}</span>
      </div>

      <Card className="flex flex-col overflow-hidden">
        {rows.length === 0 ? (
          <EmptyState
            title={period ? tr.empty.reconciliation : tr.reconciliation.noPeriod}
            hint={period ? tr.empty.reconciliationHint : tr.reconciliation.noPeriodHint}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-cell">
                <thead>
                  <tr>
                    <Head align="left" className="pl-5">
                      {tr.reconciliation.type}
                    </Head>
                    <Head align="left">{tr.reconciliation.orderRef}</Head>
                    <Head>{tr.reconciliation.expected}</Head>
                    <Head>{tr.reconciliation.actual}</Head>
                    <Head>{tr.reconciliation.diff}</Head>
                    <Head align="left">{tr.reconciliation.status}</Head>
                    <Head align="left" className="pr-5">
                      {tr.reconciliation.note}
                    </Head>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((diff) => (
                    <DiffRow key={diff.id} brand={params.brand} diff={diff} />
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap items-center gap-3 border-t border-hairline bg-canvas px-5 py-2.5 text-helper text-ink-body">
              <span>
                {tr.reconciliation.showingDiffs
                  .replace("{shown}", formatCount(rows.length))
                  .replace("{total}", formatCount(all.length))}
              </span>
              <span className="text-ink-ghost">·</span>
              <span>
                {tr.reconciliation.openDiff} {formatMoney(totals?.open_diff ?? 0)}
              </span>
            </div>
          </>
        )}
      </Card>
    </>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="col-head">{label}</span>
      <span className={`text-kpiSm ${tone ?? ""}`}>{value}</span>
    </div>
  );
}

function Head({
  children,
  align = "right",
  className = "",
}: {
  children: React.ReactNode;
  /** Hizalama prop'tur, sınıfla ezilmez (bkz. `sku-table.tsx`). */
  align?: "left" | "right";
  className?: string;
}) {
  return (
    <th
      className={`sticky top-0 z-[5] border-b border-hairline bg-canvas px-3 py-2.5 ${
        align === "left" ? "text-left" : "text-right"
      } ${className}`}
    >
      <span className="col-head">{children}</span>
    </th>
  );
}

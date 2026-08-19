/**
 * Hakediş mutabakatı ekranı (spec §7.4).
 *
 * Tek soru: platformun kestiği tutar bizim hesabımızla aynı mı? Ekran dönem bazında
 * eşleşme oranını, açık farkları ve "açıklandı" akışını gösterir.
 */

import { KpiCard } from "@/components/kpi-card";
import { DiffRow, ReconciliationRunner } from "@/components/reconciliation-panel";
import { Card, EmptyState, SectionHeader, Th } from "@/components/ui";
import {
  fetchReconciliationDiffs,
  fetchReconciliationPeriods,
  fetchReconciliationSummary,
} from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatCount, formatMoney } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function ReconciliationPage({
  params,
  searchParams,
}: {
  params: { brand: BrandSlug };
  searchParams: { period?: string };
}) {
  const periodList = await fetchReconciliationPeriods(params.brand);
  const periods = periodList.ok ? periodList.data : [];
  const period = searchParams.period ?? periods[0] ?? "";

  const [diffs, summary] = await Promise.all([
    fetchReconciliationDiffs(params.brand, period || undefined),
    period
      ? fetchReconciliationSummary(params.brand, period)
      : Promise.resolve({ ok: false as const, status: 404, reason: "no-period" }),
  ]);

  const rows = diffs.ok ? diffs.data : [];
  const totals = summary.ok ? summary.data : null;

  return (
    <>
      <h1 className="text-lg font-medium">{tr.reconciliation.title}</h1>
      <p className="-mt-4 text-xs text-ink-faint">{tr.reconciliation.subtitle}</p>

      <div className="grid gap-4 sm:grid-cols-4">
        <KpiCard
          label={tr.reconciliation.diffs}
          value={formatCount(totals?.diff_count ?? 0)}
          hint={period || undefined}
        />
        <KpiCard
          label={tr.reconciliation.openCount}
          value={formatCount(totals?.open_count ?? 0)}
          tone={totals && totals.open_count > 0 ? "negative" : "neutral"}
        />
        <KpiCard
          label={tr.reconciliation.explainedCount}
          value={formatCount((totals?.explained_count ?? 0) + (totals?.resolved_count ?? 0))}
        />
        <KpiCard
          label={tr.reconciliation.totalDiff}
          value={formatMoney(totals?.total_diff ?? 0)}
        />
      </div>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.reconciliation.run} subtitle={tr.reconciliation.diffsSubtitle} />
        <ReconciliationRunner brand={params.brand} periods={periods} />
      </Card>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.reconciliation.diffsTitle} />
        </div>
        {rows.length === 0 ? (
          <EmptyState title={tr.empty.reconciliation} hint={tr.empty.reconciliationHint} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-surface">
                <tr className="border-b border-hairline text-xs font-medium text-ink-faint">
                  <Th>{tr.table.date}</Th>
                  <Th align="right">{tr.reconciliation.expected}</Th>
                  <Th align="right">{tr.reconciliation.actual}</Th>
                  <Th align="right">{tr.reconciliation.diff}</Th>
                  <Th>{tr.reconciliation.status}</Th>
                  <Th>{tr.reconciliation.note}</Th>
                  <Th align="right">{tr.table.detail}</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((diff) => (
                  <DiffRow key={diff.id} brand={params.brand} diff={diff} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

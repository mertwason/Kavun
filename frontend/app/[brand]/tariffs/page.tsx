/** Komisyon tarifeleri — güncel oranlar, değişiklik geçmişi, etki analizi (spec §12B). */

import { TariffImpact } from "@/components/tariff-impact";
import { TariffUpload } from "@/components/tariff-upload";
import {
  Card,
  DataTable,
  EmptyState,
  ErrorState,
  SectionHeader,
  Td,
  Th,
  Tr,
} from "@/components/ui";
import { fetchCommissionChanges, fetchCommissionRates } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatDate, formatMoney, formatPercent, signClass, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const SOURCE_LABELS: Record<string, string> = tr.commissionSource;

export default async function TariffsPage({ params }: { params: { brand: BrandSlug } }) {
  const [rates, changes] = await Promise.all([
    fetchCommissionRates(params.brand),
    fetchCommissionChanges(params.brand),
  ]);

  const categories = rates.ok
    ? Array.from(
        new Set(rates.data.map((rate) => rate.category_code).filter((code): code is string =>
          Boolean(code),
        )),
      ).sort()
    : [];

  return (
    <>
      <h1 className="text-lg font-medium">{tr.nav.tariffs}</h1>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.tariffs.uploadTitle} subtitle={tr.tariffs.uploadSubtitle} />
        <TariffUpload brand={params.brand} />
      </Card>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.tariffs.impactTitle} subtitle={tr.tariffs.impactSubtitle} />
        <TariffImpact brand={params.brand} categories={categories} />
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="flex flex-col">
          <div className="p-5 pb-2">
            <SectionHeader title={tr.tariffs.currentTitle} />
          </div>
          {!rates.ok ? (
            <ErrorState status={rates.status} />
          ) : rates.data.length === 0 ? (
            <EmptyState title={tr.empty.tariffs} hint={tr.empty.tariffsHint} />
          ) : (
            <DataTable
              head={
                <>
                  <Th>{tr.table.category}</Th>
                  <Th align="right">{tr.tariffs.rate}</Th>
                  <Th>{tr.tariffs.source}</Th>
                  <Th>{tr.tariffs.validFrom}</Th>
                </>
              }
            >
              {rates.data.map((rate) => (
                <Tr key={rate.id}>
                  <Td>{rate.category_code ?? tr.tariffs.productScope}</Td>
                  <Td align="right">{formatPercent(toNumber(rate.rate) * 100)}</Td>
                  <Td className="text-ink-muted">
                    {SOURCE_LABELS[rate.source] ?? rate.source}
                  </Td>
                  <Td className="text-ink-muted">{formatDate(rate.valid_from)}</Td>
                </Tr>
              ))}
            </DataTable>
          )}
        </Card>

        <Card className="flex flex-col">
          <div className="p-5 pb-2">
            <SectionHeader title={tr.tariffs.historyTitle} subtitle={tr.tariffs.historySubtitle} />
          </div>
          {!changes.ok ? (
            <ErrorState status={changes.status} />
          ) : changes.data.length === 0 ? (
            <EmptyState title={tr.empty.tariffChanges} hint={tr.empty.tariffChangesHint} />
          ) : (
            <DataTable
              head={
                <>
                  <Th>{tr.table.category}</Th>
                  <Th align="right">{tr.tariffs.oldRate}</Th>
                  <Th align="right">{tr.tariffs.newRate}</Th>
                  <Th align="right">{tr.tariffs.monthlyImpact}</Th>
                  <Th>{tr.table.date}</Th>
                </>
              }
            >
              {changes.data.map((change) => (
                <Tr
                  key={change.id}
                  negative={toNumber(change.monthly_profit_impact ?? 0) < 0}
                >
                  <Td>{change.category_code ?? "—"}</Td>
                  <Td align="right">{formatPercent(toNumber(change.old_rate) * 100)}</Td>
                  <Td align="right">{formatPercent(toNumber(change.new_rate) * 100)}</Td>
                  <Td align="right" className={signClass(change.monthly_profit_impact ?? 0)}>
                    {change.monthly_profit_impact === null
                      ? "—"
                      : formatMoney(change.monthly_profit_impact)}
                  </Td>
                  <Td className="text-ink-muted">{formatDate(change.detected_at)}</Td>
                </Tr>
              ))}
            </DataTable>
          )}
        </Card>
      </div>
    </>
  );
}

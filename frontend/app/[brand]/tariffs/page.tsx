/**
 * Komisyon tarifeleri — handoff `Komisyon Tarifeleri.dc.html` (spec §12B).
 *
 * İki sekme: geçerli oranlar ve değişiklik geçmişi. Geçmiş satırları **kart** olarak
 * çizilir çünkü asıl bilgi oranın kendisi değil, değişimin parasal etkisidir.
 *
 * **Tasarımdan sapma:** handoff kartlarda "etkilenen SKU" ve "negatif marja düşen" sayısını
 * gösteriyor; bu sayılar `commission_changes` tablosunda saklanmıyor (yalnızca aylık kâr
 * etkisi saklanıyor). Uydurmak yerine kart, etki panelini o kategoriyle açan bir bağlantı
 * veriyor — sayılar canlı hesaplanıp orada çıkıyor.
 */

import Link from "next/link";

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
import {
  formatCount,
  formatDate,
  formatMoney,
  formatPercent,
  signClass,
  toNumber,
} from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const SOURCE_LABELS: Record<string, string> = tr.commissionSource;

type Search = { tab?: string; impact?: string };

export default async function TariffsPage({
  params,
  searchParams,
}: {
  params: { brand: BrandSlug };
  searchParams: Search;
}) {
  const [rates, changes] = await Promise.all([
    fetchCommissionRates(params.brand),
    fetchCommissionChanges(params.brand),
  ]);

  const tab = searchParams.tab === "history" ? "history" : "current";
  const categories = rates.ok
    ? Array.from(
        new Set(
          rates.data
            .map((rate) => rate.category_code)
            .filter((code): code is string => Boolean(code)),
        ),
      ).sort((a, b) => a.localeCompare(b, "tr-TR"))
    : [];

  const href = (next: Search) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...searchParams, ...next })) {
      if (value) query.set(key, String(value));
    }
    return `/${params.brand}/tariffs${query.toString() ? `?${query}` : ""}`;
  };

  return (
    <>
      <h1 className="sr-only">{tr.nav.tariffs}</h1>

      <div className="flex flex-wrap items-center gap-2">
        <Tab href={href({ tab: "current" })} label={tr.tariffs.tabCurrent} active={tab === "current"} />
        <Tab
          href={href({ tab: "history" })}
          label={tr.tariffs.tabHistory}
          count={changes.ok ? changes.data.length : undefined}
          active={tab === "history"}
        />
      </div>

      {tab === "current" ? (
        <Card className="flex flex-col overflow-hidden">
          {!rates.ok ? (
            <ErrorState status={rates.status} />
          ) : rates.data.length === 0 ? (
            <EmptyState title={tr.empty.tariffs} hint={tr.empty.tariffsHint} />
          ) : (
            <>
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
                    <Td align="right" className="font-semibold">
                      {formatPercent(toNumber(rate.rate) * 100)}
                    </Td>
                    <Td>
                      <span className="badge border-hairline bg-canvas text-ink-secondary">
                        {SOURCE_LABELS[rate.source] ?? rate.source}
                      </span>
                    </Td>
                    <Td className="text-ink-secondary">{formatDate(rate.valid_from)}</Td>
                  </Tr>
                ))}
              </DataTable>

              <div className="flex flex-wrap items-center gap-3 border-t border-hairline bg-canvas px-5 py-2.5 text-helper text-ink-body">
                <span>
                  {tr.tariffs.footerCounts
                    .replace("{categories}", formatCount(categories.length))
                    .replace("{rates}", formatCount(rates.data.length))}
                </span>
                <span className="text-ink-ghost">·</span>
                <span className="text-ink-muted">{tr.tariffs.sourceNote}</span>
              </div>
            </>
          )}
        </Card>
      ) : (
        <div className="flex flex-col gap-2">
          {!changes.ok ? (
            <Card>
              <ErrorState status={changes.status} />
            </Card>
          ) : changes.data.length === 0 ? (
            <Card>
              <EmptyState title={tr.empty.tariffChanges} hint={tr.empty.tariffChangesHint} />
            </Card>
          ) : (
            changes.data.map((change) => {
              const impact = change.monthly_profit_impact;
              return (
                <Card key={change.id} className="flex flex-wrap items-center gap-x-8 gap-y-3 p-4">
                  <div className="flex min-w-[220px] flex-col gap-1">
                    <span className="col-head">{formatDate(change.detected_at)}</span>
                    <span className="text-cell font-medium">{change.category_code ?? "—"}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-cell text-ink-muted line-through">
                      {formatPercent(toNumber(change.old_rate) * 100)}
                    </span>
                    <span className="text-ink-ghost">→</span>
                    <span className="text-kpiSm">
                      {formatPercent(toNumber(change.new_rate) * 100)}
                    </span>
                  </div>

                  <div className="flex flex-col gap-0.5">
                    <span className="col-head">{tr.tariffs.monthlyImpact}</span>
                    <span className={`text-kpiSm ${signClass(impact ?? 0)}`}>
                      {impact === null ? "—" : formatMoney(impact)}
                    </span>
                  </div>

                  <div className="flex-1" />

                  {change.category_code ? (
                    <Link
                      href={href({ tab: "current", impact: change.category_code })}
                      className="flex h-7 items-center rounded-control border border-hairline bg-surface px-2.5 text-helper font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
                    >
                      {tr.tariffs.analyzeThis}
                    </Link>
                  ) : null}
                </Card>
              );
            })
          )}
        </div>
      )}

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.tariffs.impactTitle} subtitle={tr.tariffs.impactSubtitle} />
        <TariffImpact
          brand={params.brand}
          categories={categories}
          initialCategory={searchParams.impact}
        />
      </Card>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.tariffs.uploadTitle} subtitle={tr.tariffs.uploadSubtitle} />
        <TariffUpload brand={params.brand} />
      </Card>
    </>
  );
}

function Tab({
  href,
  label,
  count,
  active,
}: {
  href: string;
  label: string;
  count?: number;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "true" : undefined}
      className={`flex h-7 items-center gap-1.5 rounded-pill border px-2.5 text-helper ${
        active
          ? "border-ink bg-ink font-medium text-white"
          : "border-hairline bg-surface text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
      }`}
    >
      {label}
      {count === undefined ? null : (
        <span className={active ? "text-white/70" : "text-ink-muted"}>· {formatCount(count)}</span>
      )}
    </Link>
  );
}

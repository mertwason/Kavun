/**
 * Uyarılar ekranı (spec §10.6, tasarım brief'i kalıp 7).
 *
 * Beş ayrı akış uyarı üretiyordu ama hiçbiri görünmüyordu: negatif stok, tarife değişimi,
 * MSRP ihlali, eşleşmeyen kargo satırı, hakediş farkı ve bayat senkron. Bu ekran onları
 * tek yerde toplar ve "gördüm" akışını sunar.
 *
 * Filtreler URL'de taşınır (`?severity=&type=&status=`), böylece ekran paylaşılabilir ve
 * geri tuşu çalışır — diğer ekranlardaki dönem seçicisiyle aynı disiplin.
 */

import Link from "next/link";

import { AlertTableRow } from "@/components/alert-row";
import { KpiCard } from "@/components/kpi-card";
import { Card, EmptyState, SectionHeader, Th } from "@/components/ui";
import { fetchAlerts, fetchAlertSummary } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatCount } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const TYPE_LABELS: Record<string, string> = tr.alerts.types;

type Search = { severity?: string; type?: string; status?: string };

/** `status` sorgusunu API'nin beklediği üçlü duruma çevirir. */
function acknowledgedFilter(status: string | undefined): boolean | undefined {
  if (status === "acknowledged") return true;
  if (status === "all") return undefined;
  return false; // varsayılan: yalnızca açık uyarılar
}

export default async function AlertsPage({
  params,
  searchParams,
}: {
  params: { brand: BrandSlug };
  searchParams: Search;
}) {
  const acknowledged = acknowledgedFilter(searchParams.status);
  const [rows, summary] = await Promise.all([
    fetchAlerts(params.brand, {
      severity: searchParams.severity,
      type: searchParams.type,
      acknowledged,
    }),
    fetchAlertSummary(params.brand),
  ]);

  const alerts = rows.ok ? rows.data : [];
  const counts = summary.ok ? summary.data : null;

  return (
    <>
      <h1 className="text-lg font-medium">{tr.alerts.title}</h1>
      <p className="-mt-4 text-xs text-ink-faint">{tr.alerts.subtitle}</p>

      <div className="grid gap-4 sm:grid-cols-4">
        <KpiCard label={tr.alerts.open} value={formatCount(counts?.open ?? 0)} />
        <KpiCard
          label={tr.alerts.critical}
          value={formatCount(counts?.critical_open ?? 0)}
          tone={counts && counts.critical_open > 0 ? "negative" : "neutral"}
        />
        <KpiCard label={tr.alerts.warning} value={formatCount(counts?.warning_open ?? 0)} />
        <KpiCard label={tr.alerts.acknowledged} value={formatCount(counts?.acknowledged ?? 0)} />
      </div>

      <Card className="flex flex-col">
        <div className="flex flex-wrap items-end justify-between gap-4 p-5 pb-3">
          <SectionHeader title={tr.alerts.title} subtitle={tr.alerts.acknowledgeHint} />
          <div className="flex flex-wrap gap-4 text-xs">
            <FilterGroup
              label={tr.alerts.status}
              current={searchParams.status ?? "open"}
              options={[
                { value: "open", label: tr.alerts.open },
                { value: "acknowledged", label: tr.alerts.acknowledged },
                { value: "all", label: tr.alerts.all },
              ]}
              build={(value) => ({ ...searchParams, status: value })}
              brand={params.brand}
            />
            <FilterGroup
              label={tr.alerts.severity}
              current={searchParams.severity ?? ""}
              options={[
                { value: "", label: tr.alerts.all },
                { value: "critical", label: tr.alerts.severities.critical },
                { value: "warning", label: tr.alerts.severities.warning },
                { value: "info", label: tr.alerts.severities.info },
              ]}
              build={(value) => ({ ...searchParams, severity: value || undefined })}
              brand={params.brand}
            />
            {counts && counts.types.length > 0 ? (
              <FilterGroup
                label={tr.alerts.type}
                current={searchParams.type ?? ""}
                options={[
                  { value: "", label: tr.alerts.allTypes },
                  ...counts.types.map((type) => ({
                    value: type,
                    label: TYPE_LABELS[type] ?? type,
                  })),
                ]}
                build={(value) => ({ ...searchParams, type: value || undefined })}
                brand={params.brand}
              />
            ) : null}
          </div>
        </div>

        {alerts.length === 0 ? (
          <EmptyState title={tr.empty.alerts} hint={tr.empty.alertsHint} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-surface">
                <tr className="border-b border-hairline text-xs font-medium text-ink-faint">
                  <Th>{tr.alerts.severity}</Th>
                  <Th>{tr.alerts.type}</Th>
                  <Th>{tr.alerts.message}</Th>
                  <Th>{tr.alerts.date}</Th>
                  <Th align="right">{tr.table.detail}</Th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <AlertTableRow key={alert.id} brand={params.brand} alert={alert} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

/** Filtre şeridi — seçim URL'de taşınır, bu yüzden link (buton değil). */
function FilterGroup({
  label,
  current,
  options,
  build,
  brand,
}: {
  label: string;
  current: string;
  options: { value: string; label: string }[];
  build: (value: string) => Search;
  brand: BrandSlug;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-ink-faint">{label}</span>
      <div className="flex flex-wrap gap-1">
        {options.map((option) => {
          const query = new URLSearchParams();
          const next = build(option.value);
          for (const [key, value] of Object.entries(next)) {
            if (value) query.set(key, String(value));
          }
          const active = current === option.value;
          return (
            <Link
              key={option.value || "all"}
              href={`/${brand}/alerts${query.toString() ? `?${query}` : ""}`}
              aria-current={active ? "true" : undefined}
              className={
                active
                  ? "rounded-full border border-ink px-2.5 py-1 font-medium text-ink"
                  : "rounded-full px-2.5 py-1 text-ink-faint hover:text-ink"
              }
            >
              {option.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Uyarılar ekranı — handoff `Uyarilar.dc.html` (spec §10.6).
 *
 * Beş ayrı akış uyarı üretiyordu ama hiçbiri görünmüyordu: negatif stok, tarife değişimi,
 * MSRP ihlali, eşleşmeyen kargo satırı, hakediş farkı ve bayat senkron. Bu ekran onları
 * tek yerde toplar ve "kapat" akışını sunar.
 *
 * Liste **seviyeye göre gruplanır** (Kritik → Dikkat → Bilgi): uyarı ekranında sıralama
 * kronoloji değil aciliyettir. Filtreler URL'de taşınır (`?severity=&type=&status=`),
 * böylece ekran paylaşılabilir ve geri tuşu çalışır.
 */

import Link from "next/link";

import { AlertListRow } from "@/components/alert-row";
import { Card, EmptyState, ErrorState } from "@/components/ui";
import { fetchAlerts, fetchAlertSummary } from "@/lib/api";
import type { AlertRow } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatCount } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const TYPE_LABELS: Record<string, string> = tr.alerts.types;
const SEVERITY_LABELS: Record<string, string> = tr.alerts.severities;

/** Aciliyet sırası — gruplar bu sırayla dizilir. */
const SEVERITY_ORDER = ["critical", "warning", "info"] as const;

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

  const groups = SEVERITY_ORDER.map((severity) => ({
    severity,
    rows: alerts.filter((alert) => alert.severity === severity),
  })).filter((group) => group.rows.length > 0);

  const href = (next: Search) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(next)) {
      if (value) query.set(key, String(value));
    }
    return `/${params.brand}/alerts${query.toString() ? `?${query}` : ""}`;
  };

  return (
    <>
      <h1 className="text-title font-medium">{tr.alerts.title}</h1>
      <p className="-mt-3 text-helper text-ink-body">{tr.alerts.subtitle}</p>

      <div className="flex flex-col gap-2">
        <ChipRow label={tr.alerts.status}>
          {[
            { value: "open", label: tr.alerts.open, count: counts?.open },
            {
              value: "acknowledged",
              label: tr.alerts.acknowledged,
              count: counts?.acknowledged,
            },
            { value: "all", label: tr.alerts.all, count: counts?.total },
          ].map((option) => (
            <Chip
              key={option.value}
              href={href({ ...searchParams, status: option.value })}
              label={option.label}
              count={option.count}
              active={(searchParams.status ?? "open") === option.value}
            />
          ))}
        </ChipRow>

        <ChipRow label={tr.alerts.severity}>
          {[
            { value: "", label: tr.alerts.all, count: counts?.open },
            { value: "critical", label: SEVERITY_LABELS.critical, count: counts?.critical_open },
            { value: "warning", label: SEVERITY_LABELS.warning, count: counts?.warning_open },
            { value: "info", label: SEVERITY_LABELS.info, count: counts?.info_open },
          ].map((option) => (
            <Chip
              key={option.value || "all"}
              href={href({ ...searchParams, severity: option.value || undefined })}
              label={option.label}
              // Sayılar açık uyarıyı sayar; "Kapatılmış" görünümünde yanıltmasın.
              count={searchParams.status ? undefined : option.count}
              active={(searchParams.severity ?? "") === option.value}
            />
          ))}
        </ChipRow>

        {counts && counts.types.length > 0 ? (
          <ChipRow label={tr.alerts.type}>
            <Chip
              href={href({ ...searchParams, type: undefined })}
              label={tr.alerts.allTypes}
              active={!searchParams.type}
            />
            {counts.types.map((item) => (
              <Chip
                key={item.type}
                href={href({ ...searchParams, type: item.type })}
                label={TYPE_LABELS[item.type] ?? item.type}
                count={searchParams.status ? undefined : item.open}
                active={searchParams.type === item.type}
              />
            ))}
          </ChipRow>
        ) : null}
      </div>

      {!rows.ok ? (
        <Card>
          <ErrorState status={rows.status} />
        </Card>
      ) : groups.length === 0 ? (
        <Card>
          <EmptyState title={tr.empty.alerts} hint={tr.alerts.scanNote} />
        </Card>
      ) : (
        groups.map((group) => (
          <div key={group.severity} className="flex flex-col gap-2">
            <span data-alert-group={group.severity} className="col-head">
              {tr.alerts.openGroup
                .replace("{label}", SEVERITY_LABELS[group.severity] ?? group.severity)
                .replace("{count}", formatCount(group.rows.length))}
            </span>
            <Card className="overflow-hidden">
              {group.rows.map((alert: AlertRow) => (
                <AlertListRow key={alert.id} brand={params.brand} alert={alert} />
              ))}
            </Card>
          </div>
        ))
      )}
    </>
  );
}

function ChipRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="col-head w-16 shrink-0">{label}</span>
      {children}
    </div>
  );
}

/** Filtre çipi — seçim URL'de taşındığı için buton değil bağlantıdır. */
function Chip({
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

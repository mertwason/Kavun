"use client";

/**
 * Uyarı satırı ve kapatma akışı — handoff `Uyarilar.dc.html` (spec §10.6).
 *
 * Tablo değil **liste**: uyarı metni değişken uzunlukta, hücreye sıkıştırıldığında
 * okunmuyordu. Satır sola seviye noktasıyla başlar, altında künye (tür · ilgili kayıt ·
 * zaman), sağda "İncele" ve "Kapat" durur.
 *
 * Kapatma **tek yönlüdür**: acknowledge bir karar değil, bir okuma kaydıdır. Yanlışlıkla
 * kapatılan uyarı silinmez — "Kapatılmış" filtresinde durmaya devam eder.
 */

import Link from "next/link";
import { useState, useTransition } from "react";

import { type AckState, acknowledgeAction } from "@/app/[brand]/alerts/actions";
import type { AlertRow } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatDateTime, formatRelativeTime } from "@/lib/format";
import tr from "@/locales/tr.json";

const TYPE_LABELS: Record<string, string> = tr.alerts.types;

/** Seviye noktasının rengi (handoff: kritik kırmızı, dikkat amber, bilgi mavi). */
const SEVERITY_DOT: Record<string, string> = {
  critical: "#DC2626",
  warning: "#D97706",
  info: "#2563EB",
};

/**
 * "İncele" bağlantısı uyarının **çözüleceği** ekrana gider.
 *
 * Türü tanımadığımız bir uyarı için bağlantı basılmaz: çalışmayan bir "İncele"
 * bağlantısı, hiç olmamasından kötüdür.
 */
function inspectHref(brand: BrandSlug, alert: AlertRow): string | null {
  switch (alert.type) {
    case "negatif_stok":
      return `/${brand}/inventory`;
    case "msrp_ihlali":
    case "marj_tabani":
      return `/${brand}/sku`;
    case "komisyon_degisikligi":
      return `/${brand}/tariffs`;
    case "kargo_faturasi_eslesmedi":
      return `/${brand}/cargo`;
    case "hakedis_farki":
      return `/${brand}/reconciliation`;
    case "stale_sync":
      return `/${brand}/settings`;
    default:
      return null;
  }
}

/** `product:KHV-001` gibi künyeyi okunur hâle getirir. */
function entityLabel(entityRef: string | null): string | null {
  if (!entityRef) return null;
  const [head, ...rest] = entityRef.split(":");
  const tail = rest.join(":");
  if (!tail) return head;
  // UUID künyeler kullanıcıya bir şey anlatmaz (ör. `store:9f2c…`).
  if (/^[0-9a-f-]{36}$/i.test(tail)) return null;
  return tail;
}

export function AlertListRow({ brand, alert }: { brand: BrandSlug; alert: AlertRow }) {
  const [state, setState] = useState<AckState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const acknowledged = alert.acknowledged_at !== null;
  const href = inspectHref(brand, alert);
  const entity = entityLabel(alert.entity_ref);

  return (
    <div
      data-alert-row
      className="flex flex-wrap items-start gap-x-3 gap-y-2 border-b border-hairline px-5 py-3.5 last:border-b-0 hover:bg-canvas"
    >
      <span
        aria-hidden
        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: SEVERITY_DOT[alert.severity] ?? "#A8A29E" }}
      />

      <div className="min-w-0 flex-1">
        <p className="text-cell">{alert.message}</p>
        <p className="mt-0.5 text-helper text-ink-muted">
          {TYPE_LABELS[alert.type] ?? alert.type}
          {entity ? ` · ${entity}` : ""} ·{" "}
          {/* Göreli zaman sunucuda ve istemcide farklı dakikaya düşebilir ("7 dk" vs
              "8 dk"); bu bilinçli bir fark, hydration uyarısı üretmesin. */}
          <span suppressHydrationWarning>{formatRelativeTime(alert.created_at)}</span>
        </p>
        {state.status === "error" ? (
          <p className="mt-1 text-helper text-negative">{state.message}</p>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {href ? (
          <Link
            href={href}
            className="flex h-7 items-center rounded-control border border-hairline bg-surface px-2.5 text-helper font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
          >
            {tr.alerts.inspect}
          </Link>
        ) : null}

        {acknowledged ? (
          <span className="badge border-hairline bg-canvas text-ink-muted">
            {tr.alerts.acknowledgedAt} · {formatDateTime(alert.acknowledged_at as string)}
          </span>
        ) : (
          <button
            type="button"
            disabled={pending}
            title={tr.alerts.acknowledgeHint}
            onClick={() => {
              const formData = new FormData();
              formData.set("brand", brand);
              formData.set("alert_id", alert.id);
              startTransition(async () => {
                setState(await acknowledgeAction({ status: "idle" }, formData));
              });
            }}
            className="flex h-7 items-center rounded-control border border-hairline bg-surface px-2.5 text-helper font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
          >
            {tr.alerts.acknowledge}
          </button>
        )}
      </div>
    </div>
  );
}

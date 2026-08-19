"use client";

/**
 * Uyarı satırı ve "gördüm" akışı (spec §10.6, tasarım brief'i kalıp 7).
 *
 * Kapatma **tek yönlüdür**: acknowledge bir karar değil, bir okuma kaydıdır. Yanlışlıkla
 * kapatılan uyarı silinmez — "Kapatılmış" filtresinde durmaya devam eder.
 */

import { useState, useTransition } from "react";

import { type AckState, acknowledgeAction } from "@/app/[brand]/alerts/actions";
import type { AlertRow } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatDateTime } from "@/lib/format";
import tr from "@/locales/tr.json";

const SEVERITY_LABELS: Record<string, string> = tr.alerts.severities;
const TYPE_LABELS: Record<string, string> = tr.alerts.types;

/** Seviye rengi: kritik kırmızı, dikkat amber, bilgi nötr. */
function severityClass(severity: string): string {
  if (severity === "critical") return "text-negative";
  if (severity === "warning") return "text-estimated";
  return "text-ink-faint";
}

export function AlertTableRow({ brand, alert }: { brand: BrandSlug; alert: AlertRow }) {
  const [state, setState] = useState<AckState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const acknowledged = alert.acknowledged_at !== null;

  return (
    <tr className="border-b border-hairline align-top">
      <td className={`px-3 py-2 whitespace-nowrap ${severityClass(alert.severity)}`}>
        {SEVERITY_LABELS[alert.severity] ?? alert.severity}
      </td>
      <td className="px-3 py-2 whitespace-nowrap text-ink-muted">
        {TYPE_LABELS[alert.type] ?? alert.type}
      </td>
      <td className="px-3 py-2">{alert.message}</td>
      <td className="px-3 py-2 whitespace-nowrap text-ink-muted">
        {formatDateTime(alert.created_at)}
      </td>
      <td className="px-3 py-2 text-right whitespace-nowrap">
        {acknowledged ? (
          <span className="text-xs text-ink-faint">
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
            className="text-sm text-ink-muted underline underline-offset-4 hover:text-ink disabled:opacity-40"
          >
            {tr.alerts.acknowledge}
          </button>
        )}
        {state.status === "error" ? (
          <span className="ml-2 text-xs text-negative">{state.message}</span>
        ) : null}
      </td>
    </tr>
  );
}

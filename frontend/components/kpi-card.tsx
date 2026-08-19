/** Dashboard KPI kartı — büyük, ince, tabular rakam; sembol rakamdan küçük. */

import type { ReactNode } from "react";

export function KpiCard({
  label,
  value,
  hint,
  tone = "neutral",
  footer,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "positive" | "negative";
  footer?: ReactNode;
}) {
  const toneClass =
    tone === "positive" ? "text-positive" : tone === "negative" ? "text-negative" : "text-ink";
  return (
    <div className="card flex flex-col gap-1 p-5">
      <span className="text-xs font-medium uppercase tracking-wide text-ink-faint">{label}</span>
      <span className={`tabular text-kpi ${toneClass}`}>{value}</span>
      {hint ? <span className="text-xs text-ink-faint">{hint}</span> : null}
      {footer ? <div className="mt-2 border-t border-hairline pt-2 text-xs">{footer}</div> : null}
    </div>
  );
}

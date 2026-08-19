/** Uyarı seviyesi noktası — kritik kırmızı, dikkat amber, bilgi gri (handoff §10). */

const COLORS: Record<string, string> = {
  critical: "bg-negative",
  warning: "bg-estimated",
  info: "bg-ink-ghost",
};

export function AlertDot({ severity }: { severity: string }) {
  return (
    <span
      aria-hidden
      className={`inline-block h-1.5 w-1.5 shrink-0 rounded-pill ${COLORS[severity] ?? "bg-ink-ghost"}`}
    />
  );
}

/**
 * Ortak arayüz parçaları — tasarım brief'i bağlayıcıdır.
 *
 * Kurallar: gölge yok (yalnızca 1px hairline), anlam taşıyan renk yalnızca veri için,
 * rakamlar tabular-nums, renk tek başına anlam taşımaz (rozet/işaret eşlik eder).
 */

import Link from "next/link";
import type { ReactNode } from "react";

import tr from "@/locales/tr.json";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <h2 className="text-body font-medium text-ink">{title}</h2>
      {subtitle ? <p className="text-helper text-ink-body">{subtitle}</p> : null}
    </div>
  );
}

/**
 * "Tahmini vs kesinleşmiş" ayrımı (tasarım brief'i, kalıp 2).
 * Tooltip'e gömülmez — hücre seviyesinde görünür.
 */
export function EstimateBadge({ isFinal }: { isFinal: boolean }) {
  if (isFinal) {
    return (
      <span className="badge border-hairline bg-canvas text-ink-secondary">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-ink-faint" />
        {tr.estimate.final}
      </span>
    );
  }
  return (
    <span className="badge border-estimated-border bg-estimated-tint text-estimated-text">
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-estimated" />
      {tr.estimate.estimated}
    </span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center gap-1.5 px-6 py-16 text-center">
      <p className="text-cell font-medium text-ink-secondary">{title}</p>
      {hint ? <p className="max-w-md text-helper text-ink-muted">{hint}</p> : null}
    </div>
  );
}

export function ErrorState({ status }: { status: number }) {
  const title = status === 404 ? tr.error.notFound : tr.error.unreachable;
  const hint = status === 404 ? undefined : tr.error.unreachableHint;
  return <EmptyState title={title} hint={hint} />;
}

/** Veri yoğun tablo iskeleti: sticky header, compact satır, hover vurgusu (kalıp 3). */
export function DataTable({
  head,
  children,
}: {
  head: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-cell">
        <thead>
          <tr>{head}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Th({
  children,
  align = "left",
}: {
  children: ReactNode;
  /** Hizalama prop'tur, sınıfla EZİLMEZ: `text-left`/`text-right` aynı özgüllükte. */
  align?: "left" | "right";
}) {
  return (
    <th
      className={`sticky top-0 z-[5] border-b border-hairline bg-canvas px-3 py-2.5 ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      <span className="col-head">{children}</span>
    </th>
  );
}

export function Td({
  children,
  align = "left",
  className = "",
}: {
  children: ReactNode;
  align?: "left" | "right";
  className?: string;
}) {
  return (
    <td className={`px-3 py-2.5 ${align === "right" ? "text-right" : ""} ${className}`}>
      {children}
    </td>
  );
}

/** Negatif marj satırı hafif kırmızı zemin alır (handoff: `#FEF7F7`). */
export function Tr({
  children,
  negative = false,
  href,
}: {
  children: ReactNode;
  negative?: boolean;
  href?: string;
}) {
  const className = `border-b border-hairline ${
    negative ? "bg-negative-row" : "hover:bg-canvas"
  }`;
  if (!href) {
    return <tr className={className}>{children}</tr>;
  }
  return <tr className={`${className} cursor-pointer`}>{children}</tr>;
}

export function TextLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="text-cell text-ink-secondary underline decoration-ink-ghost underline-offset-4 hover:text-ink"
    >
      {children}
    </Link>
  );
}

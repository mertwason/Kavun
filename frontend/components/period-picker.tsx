/**
 * Dönem seçici (spec §10.1).
 *
 * Sunucu bileşeni: seçim URL'e yazılır (`?days=90`), böylece sayfa paylaşılabilir
 * ve geri tuşu çalışır — istemci state'i taşımaya gerek yok.
 */

import Link from "next/link";

import tr from "@/locales/tr.json";

export const PERIOD_OPTIONS = [
  { days: 7, label: tr.period.last7 },
  { days: 30, label: tr.period.last30 },
  { days: 90, label: tr.period.last90 },
  { days: 365, label: tr.period.last365 },
];

export const DEFAULT_DAYS = 30;

/** `?days=` değerini güvenli aralığa sıkıştırır. */
export function resolveDays(raw: string | string[] | undefined): number {
  const value = Number(Array.isArray(raw) ? raw[0] : raw);
  const match = PERIOD_OPTIONS.find((option) => option.days === value);
  return match ? match.days : DEFAULT_DAYS;
}

/** Dönemi `from`/`to` (ISO tarih) çiftine çevirir; `to` hariçtir. */
export function periodRange(days: number): { from: string; to: string } {
  const today = new Date();
  const end = new Date(today);
  end.setDate(end.getDate() + 1);
  const start = new Date(today);
  start.setDate(start.getDate() - (days - 1));
  const iso = (value: Date) => value.toISOString().slice(0, 10);
  return { from: iso(start), to: iso(end) };
}

export function PeriodPicker({
  basePath,
  activeDays,
}: {
  basePath: string;
  activeDays: number;
}) {
  return (
    <div className="flex items-center gap-1 text-xs">
      <span className="mr-1 text-ink-faint">{tr.period.label}</span>
      {PERIOD_OPTIONS.map((option) => (
        <Link
          key={option.days}
          href={`${basePath}?days=${option.days}`}
          aria-current={option.days === activeDays ? "page" : undefined}
          className={
            option.days === activeDays
              ? "rounded-full border border-hairline bg-surface px-2.5 py-1 font-medium text-ink"
              : "rounded-full px-2.5 py-1 text-ink-faint hover:text-ink"
          }
        >
          {option.label}
        </Link>
      ))}
    </div>
  );
}

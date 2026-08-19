/**
 * Türkçe biçimlendirme (tasarım brief'i: `1.234,56 ₺`, `29 Tem 2026`).
 *
 * API tutarları JSON'da metin olarak gelir (Decimal, kayıpsız). Burada yalnızca
 * GÖSTERİM için sayıya çevrilir; hesap yapılmaz — para matematiği backend'dedir
 * (CLAUDE.md §1).
 */

const money = new Intl.NumberFormat("tr-TR", {
  style: "currency",
  currency: "TRY",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const compact = new Intl.NumberFormat("tr-TR", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const percent = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const integer = new Intl.NumberFormat("tr-TR");

const dayMonth = new Intl.DateTimeFormat("tr-TR", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

const dayShort = new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "short" });

const dateTime = new Intl.DateTimeFormat("tr-TR", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** Metin ya da sayı olarak gelen tutarı `number`a çevirir (yalnızca gösterim için). */
export function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatMoney(value: string | number | null | undefined): string {
  return money.format(toNumber(value));
}

export function formatMoneyCompact(value: string | number | null | undefined): string {
  return `${compact.format(toNumber(value))} ₺`;
}

export function formatPercent(value: string | number | null | undefined): string {
  return `%${percent.format(toNumber(value))}`;
}

export function formatCount(value: number): string {
  return integer.format(value);
}

export function formatDate(value: string): string {
  return dayMonth.format(new Date(value));
}

export function formatDayShort(value: string): string {
  return dayShort.format(new Date(value));
}

export function formatDateTime(value: string): string {
  return dateTime.format(new Date(value));
}

/** Negatif değer kırmızı, pozitif nötr — renk tek başına anlam taşımaz, işaret de var. */
export function signClass(value: string | number | null | undefined): string {
  const parsed = toNumber(value);
  if (parsed < 0) return "text-negative";
  if (parsed > 0) return "text-positive";
  return "text-ink-muted";
}

const amount = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const rate = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

/** Dövizli tutar: para birimi ayrı sütunda durduğu için sembolsüz yazılır. */
export function formatAmount(value: string | number | null | undefined): string {
  return amount.format(toNumber(value));
}

/** Kur: 37,50 · 39,2015 — sondaki gereksiz sıfırlar atılır. */
export function formatRate(value: string | number | null | undefined): string {
  return rate.format(toNumber(value));
}

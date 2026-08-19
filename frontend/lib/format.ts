/**
 * Türkçe biçimlendirme (tasarım handoff'u: `₺1.234,56`, `−₺516,00`, `29 Tem 2026`).
 *
 * **Sembol önde.** Handoff README'si bir yerde `1.234,56 ₺` diyor ama hifi tasarım
 * dosyalarının tamamı `₺2.400,00` / `−₺516,00` biçimini kullanıyor; dosyalar "piksel
 * hedefli yeniden üretilecek" diye işaretli olduğu için onlar esas alındı. Sembolün
 * arkada olduğu tek yer kur cümlesidir ("1 € = 48,20 ₺"), o da para gösterimi değil.
 *
 * **Negatifte U+2212 (−) kullanılır**, ASCII tire değil: rakam hizasını bozmaz.
 *
 * API tutarları JSON'da metin olarak gelir (Decimal, kayıpsız). Burada yalnızca
 * GÖSTERİM için sayıya çevrilir; hesap yapılmaz — para matematiği backend'dedir
 * (CLAUDE.md §1).
 */

const MINUS = "\u2212";
const LIRA = "₺";

const moneyDigits = new Intl.NumberFormat("tr-TR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const moneyDigitsWhole = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });

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
  const parts = formatMoneyParts(value);
  return `${parts.sign}${parts.symbol}${parts.digits}`;
}

/** Kuruşsuz tutar (KPI ve özet satırları: `₺284.650`). */
export function formatMoneyWhole(value: string | number | null | undefined): string {
  const parts = formatMoneyParts(value, { whole: true });
  return `${parts.sign}${parts.symbol}${parts.digits}`;
}

/**
 * Tutarın parçaları — KPI'da ₺ simgesi rakamdan bir kademe küçük ve soluk çizilir,
 * bu yüzden bileşenin parçalara ayrı ayrı erişmesi gerekir (handoff, Tipografi).
 */
export function formatMoneyParts(
  value: string | number | null | undefined,
  options: { whole?: boolean } = {},
): { sign: string; symbol: string; digits: string } {
  const parsed = toNumber(value);
  const formatter = options.whole ? moneyDigitsWhole : moneyDigits;
  return {
    sign: parsed < 0 ? MINUS : "",
    symbol: LIRA,
    digits: formatter.format(Math.abs(parsed)),
  };
}

export function formatMoneyCompact(value: string | number | null | undefined): string {
  return `${compact.format(toNumber(value))} ₺`;
}

export function formatPercent(value: string | number | null | undefined): string {
  const parsed = toNumber(value);
  const sign = parsed < 0 ? MINUS : "";
  return `${sign}%${percent.format(Math.abs(parsed))}`;
}

/** Puan farkı: `+1,2 pt` / `−1,2 pt` (handoff: marj deltası puan olarak yazılır). */
export function formatPoint(value: string | number | null | undefined): string {
  const parsed = toNumber(value);
  const sign = parsed < 0 ? MINUS : "+";
  return `${sign}${percent.format(Math.abs(parsed))} pt`;
}

export function formatCount(value: number): string {
  return integer.format(value);
}

/** Desi/ölçü değeri: Türkçe ondalık ayırıcı, gereksiz sondaki sıfırlar atılır (2,5 · 10). */
export function formatDesi(value: string | number | null | undefined): string {
  return new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 2 }).format(toNumber(value));
}

/** Sayısal alanın form girdisi hâli: nokta ondalık, sondaki sıfırlar atılmış (8.99). */
export function toInputNumber(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "";
  const parsed = toNumber(value);
  return String(parsed);
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

/** "12 dk önce" — topbar senkron göstergesi (handoff). */
export function formatRelativeTime(value: string): string {
  const then = new Date(value).getTime();
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (minutes < 1) return "az önce";
  if (minutes < 60) return `${minutes} dk önce`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} sa önce`;
  return `${Math.round(hours / 24)} gün önce`;
}

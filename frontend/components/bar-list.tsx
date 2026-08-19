/**
 * Kanal kırılımı bar listesi — handoff `Dashboard.dc.html`.
 *
 * Satır: harf rozeti + ad + tutar + %pay; altında 8px track (`#F5F5F4`) üzerinde stone
 * tonlu dolgu. Renk burada **anlam taşımaz** — sıralama zaten uzunlukla okunuyor, bu
 * yüzden semantik palet kullanılmaz.
 */

import { formatPercent } from "@/lib/format";

export type BarRow = {
  key: string;
  initial: string;
  label: string;
  value: number;
  display: string;
};

export function BarList({ rows }: { rows: BarRow[] }) {
  const total = rows.reduce((sum, row) => sum + Math.max(0, row.value), 0);

  return (
    <div className="flex flex-col gap-3">
      {rows.map((row) => {
        const share = total > 0 ? (Math.max(0, row.value) / total) * 100 : 0;
        return (
          <div key={row.key} className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2 text-cell">
              <span
                aria-hidden
                className="inline-flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[5px] bg-divider text-[10px] font-semibold text-ink-secondary"
              >
                {row.initial}
              </span>
              <span className="min-w-0 flex-1 truncate">{row.label}</span>
              <span className="font-medium">{row.display}</span>
              <span className="w-12 text-right text-ink-muted">{formatPercent(share)}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-pill bg-divider">
              <div className="h-full rounded-pill bg-ink-body" style={{ width: `${share}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

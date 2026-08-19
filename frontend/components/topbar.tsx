"use client";

/**
 * Üst çubuk — handoff `Dashboard.dc.html` (56px, beyaz, sticky, alt hairline).
 *
 * Solda breadcrumb ("Grup / Sayfa"), sağda dönem seçici, senkron durumu, zil + okunmamış
 * sayacı ve avatar. Senkron noktası yeşil (canlı) ya da gri ("Henüz senkron yok") —
 * boş kurulumda sayaç da görünmez, çünkü gösterecek uyarı yoktur.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Calendar, ChevronDown } from "lucide-react";

import type { BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

/** Rota → breadcrumb eşlemesi; sidebar gruplarından türetilir. */
export type Crumbs = Record<string, { group: string; label: string }>;

export function Topbar({
  brand,
  crumbs,
  fallbackPage,
  periodLabel,
  syncLabel,
  synced,
  alertCount,
  initials,
}: {
  brand: BrandSlug;
  crumbs: Crumbs;
  fallbackPage: string;
  periodLabel: string;
  syncLabel: string;
  synced: boolean;
  alertCount: number;
  initials: string;
}) {
  const pathname = usePathname();
  const crumb = resolveCrumb(pathname, crumbs);
  const group = crumb?.group ?? "";
  const page = crumb?.label ?? fallbackPage;

  return (
    <header className="sticky top-0 z-20 flex h-topbar shrink-0 items-center justify-between border-b border-hairline bg-surface px-6">
      <div className="flex min-w-0 items-center gap-2">
        {group ? (
          <>
            <span className="text-helper text-ink-muted">{group}</span>
            <span className="text-helper text-ink-ghost">/</span>
          </>
        ) : null}
        <span className="truncate text-body font-semibold">{page}</span>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          className="flex h-8 items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 text-cell text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
        >
          <Calendar className="h-3.5 w-3.5 text-ink-body" aria-hidden />
          <span>{periodLabel}</span>
          <ChevronDown className="h-3 w-3 text-ink-muted" aria-hidden />
        </button>

        <div className="flex items-center gap-1.5 text-helper text-ink-body">
          <span
            aria-hidden
            className={`inline-block h-1.5 w-1.5 rounded-pill ${
              synced ? "bg-positive" : "bg-ink-ghost"
            }`}
          />
          <span className={synced ? undefined : "text-ink-muted"}>{syncLabel}</span>
        </div>

        <Link
          href={`/${brand}/alerts`}
          aria-label={tr.nav.alerts}
          className="relative flex h-8 w-8 items-center justify-center rounded-control hover:bg-divider"
        >
          <Bell className="h-4 w-4 text-ink-secondary" aria-hidden />
          {alertCount > 0 ? (
            <span className="absolute right-px top-px inline-flex h-[15px] min-w-[15px] items-center justify-center rounded-pill border-2 border-surface bg-negative px-0.5 text-[9.5px] font-semibold text-white">
              {alertCount}
            </span>
          ) : null}
        </Link>

        <span
          aria-hidden
          className="inline-flex h-7 w-7 items-center justify-center rounded-pill bg-divider text-[11px] font-semibold text-ink-secondary"
        >
          {initials}
        </span>
      </div>
    </header>
  );
}

/** En uzun eşleşen yol kazanır: `/x/orders/123` sipariş detayında da "Siparişler" der. */
function resolveCrumb(pathname: string, crumbs: Crumbs) {
  let best: { group: string; label: string } | undefined;
  let bestLength = -1;
  for (const [href, crumb] of Object.entries(crumbs)) {
    const matches = pathname === href || pathname.startsWith(`${href}/`);
    if (matches && href.length > bestLength) {
      best = crumb;
      bestLength = href.length;
    }
  }
  return best;
}

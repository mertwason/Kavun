"use client";

/**
 * Sol kenar çubuğu — `docs/design_handoff_kavun/Sidebar.dc.html` (KVN-EK-08).
 *
 * 240px, sticky, tam boy. Üstte workspace switcher (rozet + ad + chevron → Holding),
 * ortada gruplu nav, altta plan bloğu + wordmark.
 *
 * **Aktif öğe kalıbı (bağlayıcı):** beyaz zemin + `inset 2px 0 0 <aksan>` sol çizgi +
 * `inset 0 0 0 1px #E7E5E4` çerçeve + aksan renkli metin/ikon. Aksan rengi uygulamada
 * yalnızca burada, birincil butonda ve workspace rozetinde görünür.
 *
 * Handoff'un nav listesi 11 öğe sayıyor; Kavun'da bunlara ek olarak çalışan dört ekran
 * daha var (taslak ürün, kargo faturaları, ithalat dosyaları, D2B). Silinmediler —
 * çalışan özelliği tasarım listesinde yok diye kaldırmak veri/işlev kaybı olurdu; en
 * yakın gruba yerleştirildiler. Bayrağa bağlı olanlar (ithalat, D2B) kapalı markada
 * menüde hiç görünmez (spec §3A.4).
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bell,
  Boxes,
  ChevronsUpDown,
  FileUp,
  GitCompareArrows,
  LayoutDashboard,
  type LucideIcon,
  Package,
  Percent,
  Scale,
  Settings,
  ShoppingCart,
  Ship,
  Sparkles,
  Store,
  Truck,
  TrendingUp,
} from "lucide-react";

import type { BrandInfo } from "@/lib/brands";
import tr from "@/locales/tr.json";

/**
 * İkon **anahtar** olarak taşınır, bileşen olarak değil: sidebar bir istemci bileşeni,
 * onu besleyen layout ise sunucu bileşeni. React bileşen referansı bu sınırdan geçemez
 * (RSC manifest hatası), serileştirilebilir anahtar geçer.
 */
export type NavIconKey = keyof typeof NAV_ICONS;

export type NavItem = {
  href: string;
  label: string;
  icon: NavIconKey;
  /** Kırmızı sayaç rozeti (yalnızca Uyarılar). */
  badge?: number;
};

export type NavGroup = { title: string; items: NavItem[] };

export const NAV_ICONS = {
  dashboard: LayoutDashboard,
  alerts: Bell,
  orders: ShoppingCart,
  sku: TrendingUp,
  reconciliation: Scale,
  products: Package,
  drafts: Sparkles,
  scenarios: GitCompareArrows,
  tariffs: Percent,
  inventory: Boxes,
  invoices: FileUp,
  cargo: Truck,
  imports: Ship,
  d2b: Store,
  settings: Settings,
} satisfies Record<string, LucideIcon>;

export function Sidebar({
  brand,
  groups,
  planLabel,
  planUsage,
  planProgress,
}: {
  brand: BrandInfo;
  groups: NavGroup[];
  planLabel: string;
  planUsage: string;
  planProgress: number;
}) {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 flex h-screen w-sidebar shrink-0 flex-col border-r border-hairline bg-canvas text-cell">
      <div className="p-3 pb-2">
        <Link
          href="/holding"
          title={tr.workspace.switchHint}
          className="flex items-center gap-2 rounded-control border border-transparent px-2 py-[7px] hover:border-hairline hover:bg-divider"
        >
          <span
            aria-hidden
            className="inline-flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[5px] text-[10px] font-semibold text-white"
            style={{ backgroundColor: brand.accent }}
          >
            {brand.initial}
          </span>
          <span className="flex-1 truncate font-semibold text-ink">{brand.name}</span>
          <ChevronsUpDown className="h-3.5 w-3.5 text-ink-muted" aria-hidden />
        </Link>
      </div>

      <div className="mx-3 h-px bg-hairline opacity-70" />

      <nav className="flex-1 overflow-y-auto p-3 pt-[10px]">
        {groups.map((group) => (
          <div key={group.title} className="mb-1.5">
            <div className="col-head px-2 pb-1 pt-2">{group.title}</div>
            {group.items.map((item) => {
              const active = isActive(pathname, item.href);
              const Icon = NAV_ICONS[item.icon];
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`mb-px flex items-center gap-[9px] rounded-control px-2 py-1.5 font-medium ${
                    active ? "bg-surface" : "text-ink-secondary hover:bg-divider"
                  }`}
                  style={
                    active
                      ? {
                          color: brand.accent,
                          boxShadow: `inset 2px 0 0 ${brand.accent}, inset 0 0 0 1px #E7E5E4`,
                        }
                      : undefined
                  }
                >
                  <Icon
                    className="h-[15px] w-[15px] shrink-0"
                    style={{ color: active ? brand.accent : "#78716C" }}
                    aria-hidden
                  />
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.badge ? (
                    <span className="inline-flex h-[17px] min-w-[17px] items-center justify-center rounded-pill bg-negative px-1.5 text-[10px] font-semibold text-white">
                      {item.badge}
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="border-t border-hairline px-4 pb-3.5 pt-3">
        <div className="flex items-center justify-between text-micro">
          <span className="font-semibold text-ink-secondary">{planLabel}</span>
          <span className="text-ink-muted">{planUsage}</span>
        </div>
        <div className="mt-1.5 h-1 overflow-hidden rounded-pill bg-hairline">
          <div
            className="h-full rounded-pill bg-ink-body"
            style={{ width: `${Math.min(100, Math.max(0, planProgress))}%` }}
          />
        </div>
        <div className="mt-3 flex items-baseline justify-between">
          <span className="text-[12.5px] font-bold tracking-[0.01em] text-ink-secondary">
            {tr.app.wordmark}
          </span>
          <span className="text-[10.5px] text-ink-muted">{tr.app.version}</span>
        </div>
      </div>
    </aside>
  );
}

/** Dashboard yalnızca tam eşleşmede aktif; diğerleri alt rotalarında da aktif kalır. */
function isActive(pathname: string, href: string): boolean {
  const segments = href.split("/").filter(Boolean);
  if (segments.length <= 1) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

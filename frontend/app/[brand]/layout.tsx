/**
 * Marka workspace kabuğu — handoff `Sidebar.dc.html` + topbar (KVN-EK-08).
 *
 * Kullanıcı hangi markanın evreninde olduğunu asla karıştırmamalı: sidebar üstünde
 * workspace rozeti ve aktif nav öğesinde aksan çizgisi. Aksan rengi başka hiçbir yerde
 * kullanılmaz.
 *
 * Bayrağı kapalı modül menüde HİÇ görünmez — API 404 döner, menü de öğeyi çizmez
 * (spec §3A.4).
 */

import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { type NavGroup, Sidebar } from "@/components/sidebar";
import { type Crumbs, Topbar } from "@/components/topbar";
import {
  fetchAlertSummary,
  fetchImportFiles,
  fetchSession,
  fetchStores,
  fetchTierMargins,
} from "@/lib/api";
import { BRANDS, isBrandSlug } from "@/lib/brands";
import { formatRelativeTime } from "@/lib/format";
import tr from "@/locales/tr.json";

export default async function BrandLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: { brand: string };
}) {
  if (!isBrandSlug(params.brand)) {
    notFound();
  }
  const brand = BRANDS[params.brand];

  const [imports, tiers, session, alerts, stores] = await Promise.all([
    fetchImportFiles(brand.slug),
    fetchTierMargins(brand.slug),
    fetchSession(brand.slug),
    fetchAlertSummary(brand.slug),
    fetchStores(brand.slug),
  ]);

  const openAlerts = alerts.ok ? alerts.data.open : 0;
  const storeList = stores.ok ? stores.data : [];
  const lastSynced = storeList
    .map((store) => store.last_synced_at)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1);

  const groups: NavGroup[] = [
    {
      title: tr.nav.groups.overview,
      items: [
        { href: `/${brand.slug}`, label: tr.nav.dashboard, icon: "dashboard" },
        {
          href: `/${brand.slug}/alerts`,
          label: tr.nav.alerts,
          icon: "alerts",
          badge: openAlerts,
        },
      ],
    },
    {
      title: tr.nav.groups.sales,
      items: [
        { href: `/${brand.slug}/orders`, label: tr.nav.orders, icon: "orders" },
        { href: `/${brand.slug}/sku`, label: tr.nav.skuMargins, icon: "sku" },
        {
          href: `/${brand.slug}/reconciliation`,
          label: tr.nav.reconciliation,
          icon: "reconciliation",
        },
      ],
    },
    {
      title: tr.nav.groups.product,
      items: [
        { href: `/${brand.slug}/products`, label: tr.nav.products, icon: "products" },
        { href: `/${brand.slug}/drafts`, label: tr.nav.drafts, icon: "drafts" },
        { href: `/${brand.slug}/scenarios`, label: tr.nav.scenarios, icon: "scenarios" },
        { href: `/${brand.slug}/tariffs`, label: tr.nav.tariffs, icon: "tariffs" },
      ],
    },
    {
      title: tr.nav.groups.stock,
      items: [
        { href: `/${brand.slug}/inventory`, label: tr.nav.inventory, icon: "inventory" },
        { href: `/${brand.slug}/invoices`, label: tr.nav.invoices, icon: "invoices" },
        { href: `/${brand.slug}/cargo`, label: tr.nav.cargo, icon: "cargo" },
        ...(imports.ok
          ? [
              {
                href: `/${brand.slug}/imports`,
                label: tr.nav.imports,
                icon: "imports" as const,
              },
            ]
          : []),
      ],
    },
    {
      title: tr.nav.groups.admin,
      items: [
        ...(tiers.ok
          ? [{ href: `/${brand.slug}/d2b`, label: tr.nav.d2b, icon: "d2b" as const }]
          : []),
        { href: `/${brand.slug}/settings`, label: tr.nav.settings, icon: "settings" },
      ],
    },
  ];

  const user = session.ok ? session.data : null;

  // Breadcrumb, sidebar gruplarının aynasıdır: menüye eklenen ekran burada da görünür.
  const crumbs: Crumbs = Object.fromEntries(
    groups.flatMap((group) =>
      group.items.map((item) => [item.href, { group: group.title, label: item.label }]),
    ),
  );

  return (
    <div className="flex min-h-screen">
      <Sidebar
        brand={brand}
        groups={groups}
        planLabel={tr.shell.plan}
        planUsage={tr.shell.planUsage
          .replace("{used}", String(storeList.length))
          .replace("{total}", "3")}
        planProgress={(storeList.length / 3) * 100}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          brand={brand.slug}
          crumbs={crumbs}
          fallbackPage={brand.name}
          periodLabel={tr.shell.period}
          syncLabel={
            lastSynced
              ? tr.shell.syncedAgo.replace("{value}", formatRelativeTime(lastSynced))
              : tr.shell.neverSynced
          }
          synced={Boolean(lastSynced)}
          alertCount={openAlerts}
          initials={initialsOf(user?.full_name ?? user?.email ?? brand.name)}
        />

        <main className="mx-auto flex w-full max-w-content flex-col gap-4 p-6">{children}</main>
      </div>
    </div>
  );
}

/** Avatar baş harfleri: "Mert Ali" → "MA", tek kelimede ilk iki harf. */
function initialsOf(value: string): string {
  const parts = value.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toLocaleUpperCase("tr-TR");
  return value.slice(0, 2).toLocaleUpperCase("tr-TR");
}

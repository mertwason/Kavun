/**
 * Marka workspace kabuğu (tasarım brief'i, kalıp 1).
 *
 * Kullanıcı hangi markanın evreninde olduğunu asla karıştırmamalı: sol üstte marka
 * rozeti, yanında workspace switcher. Aksan rengi yalnızca rozette ve aktif nav
 * öğesinde — ekranı boyamaz.
 */

import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { BrandNav } from "@/components/brand-nav";
import { fetchImportFiles, fetchSession, fetchTierMargins } from "@/lib/api";
import { BRANDS, isBrandSlug } from "@/lib/brands";
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

  // Kapalı modül menüde görünmez: bayrak kapalıysa API 404 döner (spec §3A.4).
  const [imports, tiers, session] = await Promise.all([
    fetchImportFiles(brand.slug),
    fetchTierMargins(brand.slug),
    fetchSession(brand.slug),
  ]);

  // Workspace switcher YALNIZCA çoklu marka yetkisi olan kullanıcıya görünür (spec §3A.1);
  // tek markaya yetkili kullanıcı için diğer marka arayüzde hiç var olmaz.
  const authorized = session.ok ? session.data.brands.map((item) => item.slug) : [];
  const switchable = Object.values(BRANDS).filter((item) => authorized.includes(item.slug));
  const canSeeHolding = session.ok && session.data.is_holding_viewer;

  const navItems = [
    { href: `/${brand.slug}`, label: tr.nav.dashboard },
    { href: `/${brand.slug}/sku`, label: tr.nav.skuMargins },
    { href: `/${brand.slug}/orders`, label: tr.nav.orders },
    { href: `/${brand.slug}/products`, label: tr.nav.products },
    { href: `/${brand.slug}/drafts`, label: tr.nav.drafts },
    { href: `/${brand.slug}/scenarios`, label: tr.nav.scenarios },
    { href: `/${brand.slug}/tariffs`, label: tr.nav.tariffs },
    { href: `/${brand.slug}/invoices`, label: tr.nav.invoices },
    { href: `/${brand.slug}/inventory`, label: tr.nav.inventory },
    { href: `/${brand.slug}/cargo`, label: tr.nav.cargo },
    { href: `/${brand.slug}/reconciliation`, label: tr.nav.reconciliation },
    ...(imports.ok ? [{ href: `/${brand.slug}/imports`, label: tr.nav.imports }] : []),
    ...(tiers.ok ? [{ href: `/${brand.slug}/d2b`, label: tr.nav.d2b }] : []),
  ];

  return (
    <div className="min-h-screen">
      <header className="border-b border-hairline bg-surface">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-8 gap-y-3 px-6 py-3">
          <div className="flex items-center gap-3">
            <span
              aria-hidden
              className="h-6 w-1.5 rounded-full"
              style={{ backgroundColor: brand.accent }}
            />
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-medium">{brand.name}</span>
              <span className="text-[11px] text-ink-faint">{tr.app.name}</span>
            </div>
          </div>

          <BrandNav items={navItems} accent={brand.accent} />

          <div className="ml-auto flex items-center gap-3 text-xs">
            {switchable.length > 1 ? (
              <span className="text-ink-faint">{tr.workspace.switch}</span>
            ) : null}
            {switchable.map((item) => (
              <Link
                key={item.slug}
                href={`/${item.slug}`}
                aria-current={item.slug === brand.slug ? "page" : undefined}
                className={
                  item.slug === brand.slug
                    ? "rounded-full border border-hairline px-2.5 py-1 font-medium text-ink"
                    : "rounded-full px-2.5 py-1 text-ink-faint hover:text-ink"
                }
              >
                {item.name}
              </Link>
            ))}
            {canSeeHolding ? (
              <Link
                href="/holding"
                className="rounded-full px-2.5 py-1 text-ink-faint hover:text-ink"
              >
                {tr.nav.holding}
              </Link>
            ) : null}
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1440px] flex-col gap-6 px-6 py-8">{children}</main>
    </div>
  );
}

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

import { BRANDS, isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export default function BrandLayout({
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

  const navItems = [
    { href: `/${brand.slug}`, label: tr.nav.dashboard },
    { href: `/${brand.slug}/sku`, label: tr.nav.skuMargins },
    { href: `/${brand.slug}/orders`, label: tr.nav.orders },
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

          <nav className="flex items-center gap-5 text-sm">
            {navItems.map((item) => (
              <Link key={item.href} href={item.href} className="text-ink-muted hover:text-ink">
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3 text-xs">
            <span className="text-ink-faint">{tr.workspace.switch}</span>
            {Object.values(BRANDS).map((item) => (
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
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1440px] flex-col gap-6 px-6 py-8">{children}</main>
    </div>
  );
}

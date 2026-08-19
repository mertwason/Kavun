"use client";

/**
 * Workspace menüsü — aktif öğe vurgulanır (tasarım brief'i, kalıp 1).
 *
 * Aksan rengi yalnızca marka rozetinde ve aktif nav öğesinde kullanılır; ekranı boyamaz.
 * Menü öğeleri sunucuda hesaplanır (kapalı modül hiç gelmez), burada yalnızca "hangisi
 * aktif" kararı verilir — bu bilgi yalnızca tarayıcıda vardır.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

export type NavItem = { href: string; label: string };

export function BrandNav({ items, accent }: { items: NavItem[]; accent: string }) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap items-center gap-5 text-cell">
      {items.map((item) => {
        const active =
          pathname === item.href ||
          (item.href.split("/").length > 2 && pathname.startsWith(`${item.href}/`));
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={
              active
                ? "border-b-2 pb-0.5 font-medium text-ink"
                : "border-b-2 border-transparent pb-0.5 text-ink-muted hover:text-ink"
            }
            style={active ? { borderColor: accent } : undefined}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

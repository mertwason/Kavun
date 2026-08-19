/**
 * Workspace tanımları (spec §3A).
 *
 * Slug listesi burada sabittir çünkü rota segmenti bunlarla eşleşir; yetki kontrolü
 * backend'dedir — tanımsız slug 404 alır, yetkisiz marka da API'den 404 döner.
 */

import tr from "@/locales/tr.json";

export type BrandSlug = "alessi" | "kahveji";

export type BrandInfo = {
  slug: BrandSlug;
  name: string;
  /** Aksan rengi yalnızca rozet + aktif nav öğesi için (tasarım brief'i). */
  accent: string;
};

export const BRANDS: Record<BrandSlug, BrandInfo> = {
  alessi: { slug: "alessi", name: tr.workspace.alessi, accent: "#C8102E" },
  kahveji: { slug: "kahveji", name: tr.workspace.kahveji, accent: "#A16207" },
};

export const DEFAULT_BRAND: BrandSlug = "kahveji";

export function isBrandSlug(value: string): value is BrandSlug {
  return value === "alessi" || value === "kahveji";
}

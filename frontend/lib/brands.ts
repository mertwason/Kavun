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
  /**
   * Aksan rengi — handoff'ta YALNIZCA üç yerde kullanılır: aktif nav öğesinin sol
   * çizgisi + metni, birincil buton, workspace rozeti. Başka hiçbir yerde.
   */
  accent: string;
  /** Birincil butonun hover tonu. */
  accentHover: string;
  /** Workspace rozetindeki harf. */
  initial: string;
};

export const BRANDS: Record<BrandSlug, BrandInfo> = {
  alessi: {
    slug: "alessi",
    name: tr.workspace.alessi,
    accent: "#C8102E",
    accentHover: "#A00D25",
    initial: "A",
  },
  kahveji: {
    // Handoff Kahveji aksanını #B45309 veriyor; önceki #A16207 değeri güncellendi.
    slug: "kahveji",
    name: tr.workspace.kahveji,
    accent: "#B45309",
    accentHover: "#92400E",
    initial: "K",
  },
};

/** Holding görünümü bir marka değil ama kabukta aynı rozet kalıbını kullanır. */
export const HOLDING = { name: tr.nav.holding, accent: "#292524", initial: "H" } as const;

export const DEFAULT_BRAND: BrandSlug = "kahveji";

export function isBrandSlug(value: string): value is BrandSlug {
  return value === "alessi" || value === "kahveji";
}

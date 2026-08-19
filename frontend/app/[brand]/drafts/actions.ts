"use server";

/**
 * Taslak ürün sunucu aksiyonları (spec §12A.3, §12A.5).
 *
 * `analyze` hiçbir şey kaydetmez — form doldurulurken kâr kartını besler.
 */

import { revalidatePath } from "next/cache";

import {
  analyzeDraft,
  createDraft,
  type Draft,
  type DraftAnalysis,
  type DraftInput,
  discardDraft,
  promoteDraft,
} from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type DraftFormState = {
  status: "idle" | "analyzed" | "saved" | "promoted" | "error";
  analysis?: DraftAnalysis;
  draft?: Draft;
  message?: string;
};

function parse(formData: FormData): DraftInput | null {
  const name = String(formData.get("name") ?? "").trim();
  const price = String(formData.get("hedef_satis_fiyati") ?? "").trim();
  const cost = String(formData.get("alis_maliyeti") ?? "").trim();
  if (!name || !price || !cost) return null;

  const optional = (key: string) => {
    const value = String(formData.get(key) ?? "").trim();
    return value === "" ? null : value;
  };

  return {
    name,
    sku_onerisi: optional("sku_onerisi"),
    alis_maliyeti: cost,
    hedef_satis_fiyati: price,
    kanal: optional("kanal"),
    kategori: optional("kategori"),
    vat_rate: String(formData.get("vat_rate") ?? "20"),
    desi: optional("desi"),
    kargo_tahmini: optional("kargo_tahmini"),
  };
}

async function withBrand<T>(
  formData: FormData,
  run: (brand: "alessi" | "kahveji") => Promise<T>,
): Promise<T | DraftFormState> {
  const brand = String(formData.get("brand") ?? "");
  if (!isBrandSlug(brand)) {
    return { status: "error", message: tr.error.notFound } as DraftFormState;
  }
  return run(brand);
}

export async function analyzeAction(
  _previous: DraftFormState,
  formData: FormData,
): Promise<DraftFormState> {
  return (await withBrand(formData, async (brand) => {
    const input = parse(formData);
    if (!input) return { status: "error", message: tr.drafts.missingFields } as DraftFormState;
    const result = await analyzeDraft(brand, input);
    if (!result.ok) {
      return {
        status: "error",
        message: result.detail ?? tr.error.unreachable,
      } as DraftFormState;
    }
    return { status: "analyzed", analysis: result.data } as DraftFormState;
  })) as DraftFormState;
}

export async function saveAction(
  _previous: DraftFormState,
  formData: FormData,
): Promise<DraftFormState> {
  return (await withBrand(formData, async (brand) => {
    const input = parse(formData);
    if (!input) return { status: "error", message: tr.drafts.missingFields } as DraftFormState;
    const result = await createDraft(brand, input);
    if (!result.ok) {
      return {
        status: "error",
        message: result.detail ?? tr.error.unreachable,
      } as DraftFormState;
    }
    revalidatePath(`/${brand}/drafts`);
    return {
      status: "saved",
      draft: result.data,
      analysis: result.data.analysis,
    } as DraftFormState;
  })) as DraftFormState;
}

export async function promoteAction(brand: string, draftId: string): Promise<DraftFormState> {
  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };
  const result = await promoteDraft(brand, draftId);
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  revalidatePath(`/${brand}/drafts`);
  revalidatePath(`/${brand}/products`);
  return { status: "promoted" };
}

export async function discardAction(brand: string, draftId: string): Promise<DraftFormState> {
  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };
  const result = await discardDraft(brand, draftId);
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  revalidatePath(`/${brand}/drafts`);
  return { status: "saved", draft: result.data };
}

"use server";

/**
 * Fiyat listesi yükleme sunucu aksiyonları (spec §12A.2).
 *
 * Akış: önizle (`dry_run=true`, hiçbir şey yazılmaz) → kullanıcı onaylar → uygula.
 * Dosya iki adımda da istemciden gelir; sunucu onu saklamaz.
 */

import { revalidatePath } from "next/cache";

import { type ImportSummary, uploadPriceList } from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type UploadState = {
  status: "idle" | "preview" | "applied" | "error";
  summary?: ImportSummary;
  message?: string;
  filename?: string;
};

async function run(formData: FormData, dryRun: boolean): Promise<UploadState> {
  const brand = String(formData.get("brand") ?? "");
  const file = formData.get("file");

  if (!isBrandSlug(brand)) {
    return { status: "error", message: tr.error.notFound };
  }
  if (!(file instanceof File) || file.size === 0) {
    return { status: "error", message: tr.pricelist.noFile };
  }

  const result = await uploadPriceList(brand, file, dryRun);
  if (!result.ok) {
    return {
      status: "error",
      message: result.detail ?? tr.error.unreachable,
      filename: file.name,
    };
  }

  if (!dryRun) {
    revalidatePath(`/${brand}/products`);
  }
  return {
    status: dryRun ? "preview" : "applied",
    summary: result.data,
    filename: file.name,
  };
}

export async function previewImport(
  _previous: UploadState,
  formData: FormData,
): Promise<UploadState> {
  return run(formData, true);
}

export async function applyImport(
  _previous: UploadState,
  formData: FormData,
): Promise<UploadState> {
  return run(formData, false);
}

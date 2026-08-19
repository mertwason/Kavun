"use server";

/** D2B satış dosyası yükleme aksiyonları (spec §12C.9). */

import { revalidatePath } from "next/cache";

import { type B2BImportResult, uploadD2bSales } from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type D2bUploadState = {
  status: "idle" | "preview" | "applied" | "error";
  result?: B2BImportResult;
  message?: string;
};

async function run(formData: FormData, dryRun: boolean): Promise<D2bUploadState> {
  const brand = String(formData.get("brand") ?? "");
  const file = formData.get("file");

  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };
  if (!(file instanceof File) || file.size === 0) {
    return { status: "error", message: tr.d2b.noFile };
  }

  const result = await uploadD2bSales(brand, file, dryRun);
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  if (!dryRun) {
    revalidatePath(`/${brand}/d2b`);
    revalidatePath(`/${brand}/orders`);
  }
  return { status: dryRun ? "preview" : "applied", result: result.data };
}

export async function previewD2bUpload(
  _previous: D2bUploadState,
  formData: FormData,
): Promise<D2bUploadState> {
  return run(formData, true);
}

export async function applyD2bUpload(
  _previous: D2bUploadState,
  formData: FormData,
): Promise<D2bUploadState> {
  return run(formData, false);
}

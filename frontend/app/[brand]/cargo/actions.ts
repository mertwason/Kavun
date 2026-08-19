"use server";

/** Kargo faturası yükleme aksiyonları (spec §5.3, §6.2). */

import { revalidatePath } from "next/cache";

import { type CargoImportResult, uploadCargoInvoice } from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type CargoUploadState = {
  status: "idle" | "preview" | "applied" | "error";
  result?: CargoImportResult;
  message?: string;
};

async function run(formData: FormData, dryRun: boolean): Promise<CargoUploadState> {
  const brand = String(formData.get("brand") ?? "");
  const file = formData.get("file");
  const invoiceNo = String(formData.get("invoice_no") ?? "").trim();
  const period = String(formData.get("period") ?? "").trim();

  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };
  if (!(file instanceof File) || file.size === 0) {
    return { status: "error", message: tr.cargo.noFile };
  }
  if (!invoiceNo || !period) return { status: "error", message: tr.cargo.missingFields };

  const result = await uploadCargoInvoice(brand, file, { invoice_no: invoiceNo, period }, dryRun);
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  if (!dryRun) {
    // Kâr revize edildi: kargo ekranı da panel de tazelenmeli.
    revalidatePath(`/${brand}/cargo`);
    revalidatePath(`/${brand}`);
    revalidatePath(`/${brand}/orders`);
  }
  return { status: dryRun ? "preview" : "applied", result: result.data };
}

export async function previewCargoUpload(
  _previous: CargoUploadState,
  formData: FormData,
): Promise<CargoUploadState> {
  return run(formData, true);
}

export async function applyCargoUpload(
  _previous: CargoUploadState,
  formData: FormData,
): Promise<CargoUploadState> {
  return run(formData, false);
}

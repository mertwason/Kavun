"use server";

/** Tarife etki analizi ve dosya yükleme sunucu aksiyonları (spec §12B.2, §12B.4). */

import { revalidatePath } from "next/cache";

import { fetchTariffImpact, type TariffImpact, type TariffUpload, uploadTariff } from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type ImpactState = {
  status: "idle" | "ready" | "error";
  impact?: TariffImpact;
  message?: string;
};

export async function impactAction(
  _previous: ImpactState,
  formData: FormData,
): Promise<ImpactState> {
  const brand = String(formData.get("brand") ?? "");
  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };

  const delta = String(formData.get("rate_delta") ?? "").trim();
  if (!delta) return { status: "error", message: tr.tariffs.missingDelta };

  const category = String(formData.get("category") ?? "").trim();
  const target = String(formData.get("target_margin_pct") ?? "").trim();
  const cargo = String(formData.get("kargo_tahmini") ?? "").trim();

  // Kullanıcı yüzde girer (ör. 1,5); API oran bekler (0,015).
  const asRate = (Number(delta.replace(",", ".")) / 100).toFixed(4);

  const result = await fetchTariffImpact(brand, {
    category: category === "" ? null : category,
    new_rate: null,
    rate_delta: asRate,
    target_margin_pct: target === "" ? null : target,
    kargo_tahmini: cargo === "" ? null : cargo,
  });
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  return { status: "ready", impact: result.data };
}


export type UploadState = {
  status: "idle" | "preview" | "applied" | "error";
  result?: TariffUpload;
  message?: string;
};

async function runUpload(formData: FormData, dryRun: boolean): Promise<UploadState> {
  const brand = String(formData.get("brand") ?? "");
  const file = formData.get("file");
  const validFrom = String(formData.get("valid_from") ?? "").trim();

  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };
  if (!(file instanceof File) || file.size === 0) {
    return { status: "error", message: tr.pricelist.noFile };
  }
  if (!validFrom) return { status: "error", message: tr.tariffs.missingValidFrom };

  const result = await uploadTariff(brand, file, validFrom, dryRun);
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  if (!dryRun) {
    revalidatePath(`/${brand}/tariffs`);
  }
  return { status: dryRun ? "preview" : "applied", result: result.data };
}

export async function previewTariffUpload(
  _previous: UploadState,
  formData: FormData,
): Promise<UploadState> {
  return runUpload(formData, true);
}

export async function applyTariffUpload(
  _previous: UploadState,
  formData: FormData,
): Promise<UploadState> {
  return runUpload(formData, false);
}

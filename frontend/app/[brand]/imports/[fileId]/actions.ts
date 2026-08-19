"use server";

/** İthalat dosyası aksiyonları: masraf kalemi, ödeme, onay (spec §12C.7-8). */

import { revalidatePath } from "next/cache";

import {
  addImportCostItem,
  confirmImportFile,
  type ImportCostItemInput,
  recordImportPayment,
} from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type ImportActionState = {
  status: "idle" | "saved" | "error";
  message?: string;
};

function decimal(value: FormDataEntryValue | null): string {
  return String(value ?? "").trim().replace(",", ".");
}

export async function addCostItemAction(
  _previous: ImportActionState,
  formData: FormData,
): Promise<ImportActionState> {
  const brand = String(formData.get("brand") ?? "");
  const fileId = String(formData.get("file_id") ?? "");
  if (!isBrandSlug(brand) || !fileId) return { status: "error", message: tr.error.notFound };

  const amount = decimal(formData.get("amount_original"));
  if (!amount) return { status: "error", message: tr.imports.missingAmount };

  const rate = decimal(formData.get("fx_rate"));
  const payload: ImportCostItemInput = {
    item_type: String(formData.get("item_type") ?? "navlun") as ImportCostItemInput["item_type"],
    amount_original: amount,
    currency: String(formData.get("currency") ?? "TRY").toUpperCase(),
    fx_rate: rate === "" ? null : rate,
    vendor: String(formData.get("vendor") ?? "").trim() || null,
    doc_ref: null,
  };

  const result = await addImportCostItem(brand, fileId, payload);
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };
  revalidatePath(`/${brand}/imports/${fileId}`);
  return { status: "saved", message: tr.imports.saved };
}

export async function recordPaymentAction(
  _previous: ImportActionState,
  formData: FormData,
): Promise<ImportActionState> {
  const brand = String(formData.get("brand") ?? "");
  const fileId = String(formData.get("file_id") ?? "");
  if (!isBrandSlug(brand) || !fileId) return { status: "error", message: tr.error.notFound };

  const amount = decimal(formData.get("amount_original"));
  const rate = decimal(formData.get("fx_rate_payment"));
  const payDate = String(formData.get("pay_date") ?? "").trim();
  if (!amount || !rate || !payDate) return { status: "error", message: tr.imports.missingAmount };

  const result = await recordImportPayment(brand, fileId, {
    pay_date: payDate,
    amount_original: amount,
    fx_rate_payment: rate,
    currency: null,
  });
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };
  revalidatePath(`/${brand}/imports/${fileId}`);
  return { status: "saved", message: tr.imports.saved };
}

export async function confirmFileAction(
  _previous: ImportActionState,
  formData: FormData,
): Promise<ImportActionState> {
  const brand = String(formData.get("brand") ?? "");
  const fileId = String(formData.get("file_id") ?? "");
  if (!isBrandSlug(brand) || !fileId) return { status: "error", message: tr.error.notFound };

  const result = await confirmImportFile(brand, fileId);
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };
  revalidatePath(`/${brand}/imports/${fileId}`);
  revalidatePath(`/${brand}/inventory`);
  return { status: "saved", message: tr.imports.confirmed_ };
}

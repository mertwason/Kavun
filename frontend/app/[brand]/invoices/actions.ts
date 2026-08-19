"use server";

/** Alış faturası sunucu aksiyonları (spec §12C.3). */

import { revalidatePath } from "next/cache";

import {
  confirmInvoice,
  type InvoiceUploadResult,
  matchInvoiceLine,
  uploadInvoice,
} from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type InvoiceUploadState = {
  status: "idle" | "uploaded" | "error";
  result?: InvoiceUploadResult;
  message?: string;
};

export async function uploadAction(
  _previous: InvoiceUploadState,
  formData: FormData,
): Promise<InvoiceUploadState> {
  const brand = String(formData.get("brand") ?? "");
  const file = formData.get("file");
  const supplierId = String(formData.get("supplier_id") ?? "").trim();
  const invoiceNo = String(formData.get("invoice_no") ?? "").trim();
  const invoiceDate = String(formData.get("invoice_date") ?? "").trim();

  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };
  if (!(file instanceof File) || file.size === 0) {
    return { status: "error", message: tr.pricelist.noFile };
  }
  if (!supplierId || !invoiceNo || !invoiceDate) {
    return { status: "error", message: tr.invoices.missingFields };
  }

  const result = await uploadInvoice(brand, file, {
    supplier_id: supplierId,
    invoice_no: invoiceNo,
    invoice_date: invoiceDate,
  });
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  revalidatePath(`/${brand}/invoices`);
  return { status: "uploaded", result: result.data };
}

export type LineActionState = { status: "idle" | "done" | "error"; message?: string };

export async function matchLineAction(
  brand: string,
  invoiceId: string,
  lineId: string,
  productId: string,
): Promise<LineActionState> {
  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };
  const result = await matchInvoiceLine(brand, invoiceId, lineId, productId);
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  revalidatePath(`/${brand}/invoices/${invoiceId}`);
  return { status: "done" };
}

export async function confirmAction(brand: string, invoiceId: string): Promise<LineActionState> {
  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };
  const result = await confirmInvoice(brand, invoiceId);
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  revalidatePath(`/${brand}/invoices/${invoiceId}`);
  revalidatePath(`/${brand}/products`);
  return { status: "done" };
}

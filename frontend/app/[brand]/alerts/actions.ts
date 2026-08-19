"use server";

/** Uyarı aksiyonu: "gördüm" işareti (spec §10.6). */

import { revalidatePath } from "next/cache";

import { acknowledgeAlert } from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type AckState = {
  status: "idle" | "saved" | "error";
  message?: string;
};

export async function acknowledgeAction(
  _previous: AckState,
  formData: FormData,
): Promise<AckState> {
  const brand = String(formData.get("brand") ?? "");
  const alertId = String(formData.get("alert_id") ?? "");
  if (!isBrandSlug(brand) || !alertId) {
    return { status: "error", message: tr.error.notFound };
  }

  const result = await acknowledgeAlert(brand, alertId);
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }

  revalidatePath(`/${brand}/alerts`);
  return { status: "saved" };
}

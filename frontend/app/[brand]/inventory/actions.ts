"use server";

/** Açılış stoku ve düzeltme sunucu aksiyonları (spec §12C.4). */

import { revalidatePath } from "next/cache";

import { createAdjustment, createOpeningStock, recordDamage } from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type MovementState = {
  status: "idle" | "saved" | "error";
  message?: string;
};

/** Kullanıcı virgüllü yazabilir; API nokta ayraçlı ondalık bekler. */
function decimal(value: FormDataEntryValue | null): string {
  return String(value ?? "").trim().replace(",", ".");
}

export async function openingStockAction(
  _previous: MovementState,
  formData: FormData,
): Promise<MovementState> {
  const brand = String(formData.get("brand") ?? "");
  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };

  const productId = String(formData.get("product_id") ?? "").trim();
  if (!productId) return { status: "error", message: tr.inventory.missingProduct };

  const qty = decimal(formData.get("qty"));
  const unitCost = decimal(formData.get("unit_cost"));
  if (!qty || !unitCost) return { status: "error", message: tr.inventory.missingQty };

  const onDate = String(formData.get("on_date") ?? "").trim();
  const result = await createOpeningStock(brand, {
    product_id: productId,
    qty,
    unit_cost: unitCost,
    on_date: onDate === "" ? null : onDate,
  });
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  revalidatePath(`/${brand}/inventory`);
  return { status: "saved", message: tr.inventory.saved };
}

export async function adjustmentAction(
  _previous: MovementState,
  formData: FormData,
): Promise<MovementState> {
  const brand = String(formData.get("brand") ?? "");
  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };

  const productId = String(formData.get("product_id") ?? "").trim();
  if (!productId) return { status: "error", message: tr.inventory.missingProduct };

  const qtyDelta = decimal(formData.get("qty_delta"));
  if (!qtyDelta) return { status: "error", message: tr.inventory.missingQty };

  const reason = String(formData.get("reason") ?? "").trim();
  if (reason.length < 3) return { status: "error", message: tr.inventory.missingReason };

  const unitCost = decimal(formData.get("unit_cost"));
  const result = await createAdjustment(brand, {
    product_id: productId,
    qty_delta: qtyDelta,
    reason,
    unit_cost: unitCost === "" ? null : unitCost,
  });
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  revalidatePath(`/${brand}/inventory`);
  return { status: "saved", message: tr.inventory.saved };
}

export async function damageAction(
  _previous: MovementState,
  formData: FormData,
): Promise<MovementState> {
  const brand = String(formData.get("brand") ?? "");
  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };

  const productId = String(formData.get("product_id") ?? "").trim();
  if (!productId) return { status: "error", message: tr.inventory.missingProduct };

  const qty = decimal(formData.get("qty"));
  if (!qty) return { status: "error", message: tr.inventory.missingQty };

  const reason = String(formData.get("reason") ?? "").trim();
  if (reason.length < 3) return { status: "error", message: tr.inventory.missingReason };

  const result = await recordDamage(brand, { product_id: productId, qty, reason });
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  revalidatePath(`/${brand}/inventory`);
  return { status: "saved", message: tr.inventory.saved };
}

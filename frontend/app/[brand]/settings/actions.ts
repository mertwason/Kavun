"use server";

/**
 * Ayarlar aksiyonları (spec §10.7).
 *
 * Credential'lar burada YALNIZCA yazılır: hiçbir aksiyon içeriği geri döndürmez, form
 * kaydettikten sonra alanlar boşalır ve ekranda yalnızca "kayıtlı / girilmedi" durumu
 * görünür (CLAUDE.md §2).
 */

import { revalidatePath } from "next/cache";

import {
  closeCargoTariff,
  createCargoTariff,
  createStore,
  type CargoReestimate,
  deleteCredentials,
  reestimateCargo,
  saveCredentials,
  triggerStoreSync,
  updateStore,
} from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type FormState = {
  status: "idle" | "saved" | "error";
  message?: string;
};

export type ReestimateState = {
  status: "idle" | "preview" | "applied" | "error";
  result?: CargoReestimate;
  message?: string;
};

/** Marka slug'ını doğrular; geçersizse aksiyon hiç çalışmaz. */
function brandOf(formData: FormData): string | null {
  const brand = String(formData.get("brand") ?? "");
  return isBrandSlug(brand) ? brand : null;
}

function text(formData: FormData, key: string): string {
  return String(formData.get(key) ?? "").trim();
}

function optional(formData: FormData, key: string): string | null {
  const value = text(formData, key);
  return value === "" ? null : value;
}

export async function addStoreAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const brand = brandOf(formData);
  const name = text(formData, "name");
  const channel = text(formData, "channel");
  if (!brand || !name || !channel) return { status: "error", message: tr.error.notFound };

  const fee = optional(formData, "service_fee_per_order");
  const result = await createStore(brand, {
    channel: channel as never,
    name,
    external_seller_id: optional(formData, "external_seller_id"),
    service_fee_per_order: fee,
  });
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };

  revalidatePath(`/${brand}/settings`);
  return { status: "saved", message: tr.settings.saved };
}

export async function updateStoreAction(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const brand = brandOf(formData);
  const storeId = text(formData, "store_id");
  if (!brand || !storeId) return { status: "error", message: tr.error.notFound };

  const result = await updateStore(brand, storeId, {
    name: text(formData, "name") || null,
    external_seller_id: optional(formData, "external_seller_id"),
    service_fee_per_order: optional(formData, "service_fee_per_order"),
  });
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };

  revalidatePath(`/${brand}/settings`);
  return { status: "saved", message: tr.settings.saved };
}

export async function saveCredentialsAction(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const brand = brandOf(formData);
  const storeId = text(formData, "store_id");
  if (!brand || !storeId) return { status: "error", message: tr.error.notFound };

  // Alan adları kanala göre değişir; formdaki `cred_` önekli her alan gönderilir.
  const values: Record<string, string> = {};
  for (const [key, value] of formData.entries()) {
    if (key.startsWith("cred_") && typeof value === "string" && value.trim() !== "") {
      values[key.slice("cred_".length)] = value.trim();
    }
  }
  if (Object.keys(values).length === 0) {
    return { status: "error", message: tr.settings.credentialsMissing };
  }

  const result = await saveCredentials(brand, storeId, values);
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };

  revalidatePath(`/${brand}/settings`);
  return { status: "saved", message: tr.settings.saved };
}

export async function deleteCredentialsAction(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const brand = brandOf(formData);
  const storeId = text(formData, "store_id");
  if (!brand || !storeId) return { status: "error", message: tr.error.notFound };

  const result = await deleteCredentials(brand, storeId);
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };

  revalidatePath(`/${brand}/settings`);
  return { status: "saved", message: tr.settings.saved };
}

export async function syncStoreAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const brand = brandOf(formData);
  const storeId = text(formData, "store_id");
  if (!brand || !storeId) return { status: "error", message: tr.error.notFound };

  const result = await triggerStoreSync(brand, storeId);
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };

  revalidatePath(`/${brand}/settings`);
  return { status: "saved", message: tr.settings.syncQueued };
}

export async function addTariffAction(_previous: FormState, formData: FormData): Promise<FormState> {
  const brand = brandOf(formData);
  const desiMin = text(formData, "desi_min");
  const price = text(formData, "price");
  if (!brand || desiMin === "" || price === "") {
    return { status: "error", message: tr.error.notFound };
  }

  const result = await createCargoTariff(brand, {
    desi_min: desiMin,
    desi_max: optional(formData, "desi_max"),
    price,
    carrier: optional(formData, "carrier"),
    valid_from: optional(formData, "valid_from"),
    note: null,
  });
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };

  revalidatePath(`/${brand}/settings`);
  return { status: "saved", message: tr.settings.saved };
}

export async function closeTariffAction(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const brand = brandOf(formData);
  const tariffId = text(formData, "tariff_id");
  if (!brand || !tariffId) return { status: "error", message: tr.error.notFound };

  const result = await closeCargoTariff(brand, tariffId);
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };

  revalidatePath(`/${brand}/settings`);
  return { status: "saved", message: tr.settings.saved };
}

export async function reestimateAction(
  _previous: ReestimateState,
  formData: FormData,
): Promise<ReestimateState> {
  const brand = brandOf(formData);
  if (!brand) return { status: "error", message: tr.error.notFound };
  const dryRun = text(formData, "apply") !== "1";

  const result = await reestimateCargo(brand, dryRun);
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };
  if (!dryRun) revalidatePath(`/${brand}/settings`);

  return { status: dryRun ? "preview" : "applied", result: result.data };
}

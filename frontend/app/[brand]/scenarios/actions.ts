"use server";

/** Senaryo sunucu aksiyonları (spec §12A.4). */

import { revalidatePath } from "next/cache";

import {
  compareScenarios,
  evaluateScenario,
  saveScenario,
  type ScenarioInput,
  type ScenarioResult,
  solveTargetMargin,
  type TargetMargin,
} from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type ScenarioState = {
  status: "idle" | "evaluated" | "saved" | "compared" | "solved" | "error";
  results?: ScenarioResult[];
  target?: TargetMargin;
  message?: string;
};

function parse(formData: FormData): ScenarioInput | null {
  const productId = String(formData.get("product_id") ?? "").trim();
  const price = String(formData.get("satis_fiyati") ?? "").trim();
  if (!productId || !price) return null;

  const optional = (key: string) => {
    const value = String(formData.get(key) ?? "").trim();
    return value === "" ? null : value;
  };
  const payer = String(formData.get("kargo_kim_oder") ?? "satici");

  return {
    name: String(formData.get("name") ?? "Senaryo").trim() || "Senaryo",
    product_id: productId,
    satis_fiyati: price,
    kampanya_indirim_pct: optional("kampanya_indirim_pct"),
    kampanya_satici_pay_pct: optional("kampanya_satici_pay_pct"),
    kargo_kim_oder: payer === "alici" || payer === "platform" ? payer : "satici",
    adet_varsayimi: Number(formData.get("adet_varsayimi") ?? 1) || 1,
    commission_mode: "current",
    pinned_commission_rate: null,
    kargo_tahmini: optional("kargo_tahmini"),
  };
}

function brandOf(formData: FormData): "alessi" | "kahveji" | null {
  const brand = String(formData.get("brand") ?? "");
  return isBrandSlug(brand) ? brand : null;
}

export async function evaluateAction(
  _previous: ScenarioState,
  formData: FormData,
): Promise<ScenarioState> {
  const brand = brandOf(formData);
  const input = parse(formData);
  if (!brand || !input) return { status: "error", message: tr.scenarios.missingFields };

  const result = await evaluateScenario(brand, input);
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };
  return { status: "evaluated", results: [result.data] };
}

export async function saveAction(
  _previous: ScenarioState,
  formData: FormData,
): Promise<ScenarioState> {
  const brand = brandOf(formData);
  const input = parse(formData);
  if (!brand || !input) return { status: "error", message: tr.scenarios.missingFields };

  const result = await saveScenario(brand, input);
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };
  revalidatePath(`/${brand}/scenarios`);
  return { status: "saved", results: [result.data] };
}

export async function targetMarginAction(
  _previous: ScenarioState,
  formData: FormData,
): Promise<ScenarioState> {
  const brand = brandOf(formData);
  const input = parse(formData);
  const target = String(formData.get("hedef_marj_pct") ?? "").trim();
  if (!brand || !input || !target) {
    return { status: "error", message: tr.scenarios.missingTarget };
  }

  const result = await solveTargetMargin(brand, { ...input, hedef_marj_pct: target });
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };
  return { status: "solved", target: result.data };
}

export async function compareAction(
  brand: string,
  scenarioIds: string[],
): Promise<ScenarioState> {
  if (!isBrandSlug(brand)) return { status: "error", message: tr.error.notFound };
  const result = await compareScenarios(brand, scenarioIds);
  if (!result.ok) return { status: "error", message: result.detail ?? tr.error.unreachable };
  return { status: "compared", results: result.data };
}

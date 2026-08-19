"use server";

/** Mutabakat aksiyonları: çalıştır ve farkı açıkla (spec §7). */

import { revalidatePath } from "next/cache";

import { explainDiff, type ReconciliationRun, runReconciliation } from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type RunState = {
  status: "idle" | "preview" | "applied" | "error";
  result?: ReconciliationRun;
  message?: string;
};

async function execute(formData: FormData, dryRun: boolean): Promise<RunState> {
  const brand = String(formData.get("brand") ?? "");
  const period = String(formData.get("period") ?? "").trim();
  if (!isBrandSlug(brand) || !period) return { status: "error", message: tr.error.notFound };

  const result = await runReconciliation(brand, period, dryRun);
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  if (!dryRun) revalidatePath(`/${brand}/reconciliation`);
  return { status: dryRun ? "preview" : "applied", result: result.data };
}

export async function previewRun(_previous: RunState, formData: FormData): Promise<RunState> {
  return execute(formData, true);
}

export async function applyRun(_previous: RunState, formData: FormData): Promise<RunState> {
  return execute(formData, false);
}

export type ExplainState = {
  status: "idle" | "saved" | "error";
  message?: string;
};

export async function explainAction(
  _previous: ExplainState,
  formData: FormData,
): Promise<ExplainState> {
  const brand = String(formData.get("brand") ?? "");
  const diffId = String(formData.get("diff_id") ?? "");
  const note = String(formData.get("note") ?? "").trim();
  const status = String(formData.get("status") ?? "explained");

  if (!isBrandSlug(brand) || !diffId) return { status: "error", message: tr.error.notFound };
  if (note.length < 3) return { status: "error", message: tr.reconciliation.noteRequired };

  const result = await explainDiff(brand, diffId, {
    status: status as "explained" | "resolved",
    note,
  });
  if (!result.ok) {
    return { status: "error", message: result.detail ?? tr.error.unreachable };
  }
  revalidatePath(`/${brand}/reconciliation`);
  return { status: "saved", message: tr.reconciliation.saved };
}

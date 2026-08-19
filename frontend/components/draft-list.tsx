"use client";

/** Taslak listesi + "Ürüne Dönüştür" / "İptal" aksiyonları (spec §12A.3). */

import { useState, useTransition } from "react";

import { discardAction, promoteAction } from "@/app/[brand]/drafts/actions";
import type { Draft } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatMoney, formatPercent, signClass } from "@/lib/format";
import tr from "@/locales/tr.json";

const STATUS_LABELS: Record<string, string> = tr.drafts.status;

export function DraftList({ brand, drafts }: { brand: BrandSlug; drafts: Draft[] }) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const act = (draftId: string, promote: boolean) => {
    setError(null);
    startTransition(async () => {
      const result = promote
        ? await promoteAction(brand, draftId)
        : await discardAction(brand, draftId);
      if (result.status === "error") setError(result.message ?? null);
    });
  };

  return (
    <div className="flex flex-col gap-2">
      {error ? <p className="px-3 text-cell text-negative">{error}</p> : null}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-cell">
          <thead>
            <tr className="border-b border-hairline text-column uppercase text-ink-muted">
              <th className="px-3 py-2 text-left">{tr.drafts.name}</th>
              <th className="px-3 py-2 text-left">{tr.drafts.sku}</th>
              <th className="px-3 py-2 text-right">{tr.drafts.cost}</th>
              <th className="px-3 py-2 text-right">{tr.drafts.targetPrice}</th>
              <th className="px-3 py-2 text-right">{tr.table.profit}</th>
              <th className="px-3 py-2 text-right">{tr.table.margin}</th>
              <th className="px-3 py-2 text-left">{tr.table.state}</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {drafts.map((draft) => (
              <tr key={draft.id} className="border-b border-hairline hover:bg-canvas">
                <td className="px-3 py-2">{draft.name}</td>
                <td className="px-3 py-2 font-mono text-helper text-ink-muted">
                  {draft.sku_onerisi ?? "—"}
                </td>
                <td className="px-3 py-2 text-right tabular">
                  {formatMoney(draft.alis_maliyeti)}
                </td>
                <td className="px-3 py-2 text-right tabular">
                  {formatMoney(draft.hedef_satis_fiyati)}
                </td>
                <td className={`px-3 py-2 text-right tabular ${signClass(draft.analysis.profit)}`}>
                  {formatMoney(draft.analysis.profit)}
                </td>
                <td
                  className={`px-3 py-2 text-right tabular ${signClass(draft.analysis.margin_pct)}`}
                >
                  {formatPercent(draft.analysis.margin_pct)}
                </td>
                <td className="px-3 py-2 text-ink-muted">
                  {STATUS_LABELS[draft.status] ?? draft.status}
                </td>
                <td className="px-3 py-2 text-right">
                  {draft.status === "draft" ? (
                    <span className="flex justify-end gap-2">
                      <button
                        type="button"
                        disabled={pending}
                        onClick={() => act(draft.id, true)}
                        className="h-7 rounded-control border border-hairline bg-surface px-2.5 text-helper font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
                      >
                        {tr.drafts.promote}
                      </button>
                      <button
                        type="button"
                        disabled={pending}
                        onClick={() => act(draft.id, false)}
                        className="rounded-card px-2 py-1 text-helper text-ink-muted disabled:opacity-40 hover:text-ink"
                      >
                        {tr.drafts.discard}
                      </button>
                    </span>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

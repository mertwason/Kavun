"use client";

/**
 * Etki analizi kartı (tasarım brief'i ekran 10, spec §12B.4).
 *
 * "Komisyon %1,5 artarsa katalogda ne olur" — tek soruya tek cevap: aylık kâr etkisi,
 * negatife düşen SKU'lar ve hedef marjı koruyan yeni fiyatlar.
 */

import { useState, useTransition } from "react";

import { impactAction, type ImpactState } from "@/app/[brand]/tariffs/actions";
import type { BrandSlug } from "@/lib/brands";
import { formatMoney, formatPercent, signClass, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

export function TariffImpact({
  brand,
  categories,
}: {
  brand: BrandSlug;
  categories: string[];
}) {
  const [state, setState] = useState<ImpactState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const impact = state.impact;
  const affected = impact?.rows.filter((row) => toNumber(row.profit_impact) !== 0) ?? [];
  const negative = impact?.rows.filter(
    (row) =>
      toNumber(row.current_margin_pct) >= 0 && toNumber(row.projected_margin_pct) < 0,
  ) ?? [];

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          const formData = new FormData(event.currentTarget);
          formData.set("brand", brand);
          startTransition(async () => {
            setState(await impactAction({ status: "idle" }, formData));
          });
        }}
      >
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.table.category}</span>
          <select
            name="category"
            className="rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm"
          >
            <option value="">{tr.tariffs.allCategories}</option>
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.tariffs.rateDelta} *</span>
          <input
            name="rate_delta"
            type="number"
            step="0.1"
            defaultValue="1.5"
            required
            className="w-28 rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm tabular"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.tariffs.targetMargin}</span>
          <input
            name="target_margin_pct"
            type="number"
            step="0.1"
            placeholder={tr.tariffs.targetHint}
            className="w-32 rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm tabular"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.drafts.cargo}</span>
          <input
            name="kargo_tahmini"
            type="number"
            step="0.01"
            className="w-28 rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm tabular"
          />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="rounded-card border border-hairline px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-canvas"
        >
          {pending ? tr.pricelist.checking : tr.tariffs.analyze}
        </button>
      </form>

      {state.status === "error" ? (
        <p className="text-sm text-negative">{state.message}</p>
      ) : null}

      {impact ? (
        <>
          <div className="flex flex-wrap items-baseline gap-6 border-t border-hairline pt-3">
            <span className="flex flex-col">
              <span className="text-xs text-ink-faint">{tr.tariffs.monthlyImpact}</span>
              <span
                className={`tabular text-2xl font-medium ${signClass(impact.monthly_profit_impact)}`}
              >
                {formatMoney(impact.monthly_profit_impact)}
              </span>
            </span>
            <span className="flex flex-col">
              <span className="text-xs text-ink-faint">{tr.tariffs.affected}</span>
              <span className="tabular text-lg">{affected.length}</span>
            </span>
            <span className="flex flex-col">
              <span className="text-xs text-ink-faint">{tr.tariffs.turningNegative}</span>
              <span
                className={`tabular text-lg ${negative.length > 0 ? "text-negative" : "text-ink"}`}
              >
                {negative.length}
              </span>
            </span>
          </div>

          <div className="max-h-80 overflow-auto">
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 bg-surface">
                <tr className="border-b border-hairline text-xs font-medium text-ink-faint">
                  <th className="px-3 py-2 text-left">{tr.table.sku}</th>
                  <th className="px-3 py-2 text-left">{tr.table.product}</th>
                  <th className="px-3 py-2 text-right">{tr.tariffs.oldRate}</th>
                  <th className="px-3 py-2 text-right">{tr.tariffs.newRate}</th>
                  <th className="px-3 py-2 text-right">{tr.tariffs.currentMargin}</th>
                  <th className="px-3 py-2 text-right">{tr.tariffs.projectedMargin}</th>
                  <th className="px-3 py-2 text-right">{tr.tariffs.requiredPrice}</th>
                  <th className="px-3 py-2 text-right">{tr.tariffs.impact}</th>
                </tr>
              </thead>
              <tbody>
                {impact.rows.map((row) => {
                  const turnsNegative =
                    toNumber(row.current_margin_pct) >= 0 &&
                    toNumber(row.projected_margin_pct) < 0;
                  return (
                    <tr
                      key={row.product_id}
                      className={`border-b border-hairline ${
                        turnsNegative ? "bg-negative/[0.04]" : ""
                      }`}
                    >
                      <td className="px-3 py-1.5 font-mono text-xs text-ink-muted">{row.sku}</td>
                      <td className="px-3 py-1.5">{row.name}</td>
                      <td className="px-3 py-1.5 text-right tabular">
                        {formatPercent(toNumber(row.old_rate) * 100)}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular">
                        {formatPercent(toNumber(row.new_rate) * 100)}
                      </td>
                      <td
                        className={`px-3 py-1.5 text-right tabular ${signClass(row.current_margin_pct)}`}
                      >
                        {formatPercent(row.current_margin_pct)}
                      </td>
                      <td
                        className={`px-3 py-1.5 text-right tabular ${signClass(row.projected_margin_pct)}`}
                      >
                        {formatPercent(row.projected_margin_pct)}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular">
                        {row.required_price === null ? "—" : formatMoney(row.required_price)}
                      </td>
                      <td
                        className={`px-3 py-1.5 text-right tabular ${signClass(row.profit_impact)}`}
                      >
                        {formatMoney(row.profit_impact)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}

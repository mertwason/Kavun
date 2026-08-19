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
  initialCategory,
}: {
  brand: BrandSlug;
  categories: string[];
  /** Değişiklik geçmişinden gelen kategori — kart "etkisini hesapla" dediğinde seçili gelir. */
  initialCategory?: string;
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
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.table.category}</span>
          <select name="category" defaultValue={initialCategory ?? ""} className="control">
            <option value="">{tr.tariffs.allCategories}</option>
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.tariffs.rateDelta}</span>
          <input
            name="rate_delta"
            type="number"
            step="0.1"
            defaultValue="1.5"
            required
            className="control w-28"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.tariffs.targetMargin}</span>
          <input
            name="target_margin_pct"
            type="number"
            step="0.1"
            placeholder={tr.tariffs.targetHint}
            className="control w-32"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.drafts.cargo}</span>
          <input
            name="kargo_tahmini"
            type="number"
            step="0.01"
            className="control w-28"
          />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
        >
          {pending ? tr.pricelist.checking : tr.tariffs.analyze}
        </button>
      </form>

      {state.status === "error" ? (
        <p className="text-cell text-negative">{state.message}</p>
      ) : null}

      {impact ? (
        <>
          <div className="flex flex-wrap items-baseline gap-6 border-t border-hairline pt-3">
            <span className="flex flex-col gap-0.5">
              <span className="col-head">{tr.tariffs.monthlyImpact}</span>
              <span className={`text-kpi ${signClass(impact.monthly_profit_impact)}`}>
                {formatMoney(impact.monthly_profit_impact)}
              </span>
            </span>
            <span className="flex flex-col gap-0.5">
              <span className="col-head">{tr.tariffs.affected}</span>
              <span className="text-kpiSm">{affected.length}</span>
            </span>
            <span className="flex flex-col gap-0.5">
              <span className="col-head">{tr.tariffs.turningNegative}</span>
              <span className={`text-kpiSm ${negative.length > 0 ? "text-negative" : ""}`}>
                {negative.length}
              </span>
            </span>
          </div>

          <div className="max-h-80 overflow-auto">
            <table className="w-full border-collapse text-cell">
              <thead>
                <tr>
                  <Head align="left">{tr.table.sku}</Head>
                  <Head align="left">{tr.table.product}</Head>
                  <Head>{tr.tariffs.oldRate}</Head>
                  <Head>{tr.tariffs.newRate}</Head>
                  <Head>{tr.tariffs.currentMargin}</Head>
                  <Head>{tr.tariffs.projectedMargin}</Head>
                  <Head>{tr.tariffs.requiredPrice}</Head>
                  <Head>{tr.tariffs.impact}</Head>
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
                        turnsNegative ? "bg-negative-row" : "hover:bg-canvas"
                      }`}
                    >
                      <td className="px-3 py-2 font-mono text-micro text-ink-muted">{row.sku}</td>
                      <td className="px-3 py-2">{row.name}</td>
                      <td className="px-3 py-2 text-right">
                        {formatPercent(toNumber(row.old_rate) * 100)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {formatPercent(toNumber(row.new_rate) * 100)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right ${signClass(row.current_margin_pct)}`}
                      >
                        {formatPercent(row.current_margin_pct)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right ${signClass(row.projected_margin_pct)}`}
                      >
                        {formatPercent(row.projected_margin_pct)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {row.required_price === null ? "—" : formatMoney(row.required_price)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right ${signClass(row.profit_impact)}`}
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

function Head({
  children,
  align = "right",
}: {
  children: React.ReactNode;
  /** Hizalama prop'tur, sınıfla ezilmez (bkz. `sku-table.tsx`). */
  align?: "left" | "right";
}) {
  return (
    <th
      className={`sticky top-0 z-[5] border-b border-hairline bg-canvas px-3 py-2.5 ${
        align === "left" ? "text-left" : "text-right"
      }`}
    >
      <span className="col-head">{children}</span>
    </th>
  );
}

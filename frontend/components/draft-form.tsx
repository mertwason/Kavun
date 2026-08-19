"use client";

/**
 * Yeni Ürün Değerlendir formu + anlık kâr kartı (spec §12A.5, tasarım brief'i ekran 5).
 *
 * Form değiştikçe `analyze` çağrılır (hiçbir şey kaydedilmez); kullanıcı isterse
 * taslak olarak kaydeder, sonra listeden ürüne dönüştürür.
 */

import { useState, useTransition } from "react";

import { analyzeAction, type DraftFormState, saveAction } from "@/app/[brand]/drafts/actions";
import { Waterfall } from "@/components/waterfall";
import type { BrandSlug } from "@/lib/brands";
import { formatMoney, formatPercent, signClass, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

const WARNING_LABELS: Record<string, string> = tr.drafts.warnings;

export function DraftForm({ brand }: { brand: BrandSlug }) {
  const [state, setState] = useState<DraftFormState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const submit = (form: HTMLFormElement, save: boolean) => {
    const formData = new FormData(form);
    formData.set("brand", brand);
    startTransition(async () => {
      const action = save ? saveAction : analyzeAction;
      setState(await action({ status: "idle" }, formData));
    });
  };

  const analysis = state.analysis;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          submit(event.currentTarget, false);
        }}
      >
        <Field name="name" label={tr.drafts.name} required />
        <div className="grid grid-cols-2 gap-3">
          <Field name="sku_onerisi" label={tr.drafts.sku} placeholder={tr.drafts.skuHint} />
          <Field name="kategori" label={tr.table.category} placeholder="Kahve/Harman" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field name="alis_maliyeti" label={tr.drafts.cost} type="number" step="0.01" required />
          <Field
            name="hedef_satis_fiyati"
            label={tr.drafts.targetPrice}
            type="number"
            step="0.01"
            required
          />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <label className="flex flex-col gap-1">
            <span className="col-head">{tr.table.vat}</span>
            <select
              name="vat_rate"
              defaultValue="20"
              className="control"
            >
              <option value="0">%0</option>
              <option value="1">%1</option>
              <option value="10">%10</option>
              <option value="20">%20</option>
            </select>
          </label>
          <Field name="desi" label={tr.pricelist.desi} type="number" step="0.01" />
          <Field name="kargo_tahmini" label={tr.drafts.cargo} type="number" step="0.01" />
        </div>
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.pricelist.channel}</span>
          <select
            name="kanal"
            defaultValue="trendyol"
            className="control"
          >
            <option value="trendyol">trendyol</option>
            <option value="manual">manual (D2B)</option>
          </select>
        </label>

        <div className="mt-1 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={pending}
            className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
          >
            {pending ? tr.pricelist.checking : tr.drafts.analyze}
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={(event) => {
              const form = event.currentTarget.form;
              if (form) submit(form, true);
            }}
            className="h-[34px] rounded-control border border-ink bg-ink px-3 text-cell font-medium text-white hover:bg-ink-secondary disabled:opacity-40"
          >
            {tr.drafts.save}
          </button>
          {state.status === "saved" ? (
            <span className="text-cell text-positive-text">{tr.drafts.saved}</span>
          ) : null}
          {state.status === "error" ? (
            <span className="text-cell text-negative">{state.message}</span>
          ) : null}
        </div>
      </form>

      <div className="card flex flex-col gap-3 p-5">
        {analysis ? (
          <>
            <div className="flex items-baseline justify-between">
              <span className="col-head">
                {tr.drafts.profitCard}
              </span>
              <span className={`text-kpi ${signClass(analysis.profit)}`}>
                {formatMoney(analysis.profit)}
              </span>
            </div>
            <div className="flex items-center justify-between text-cell">
              <span className="col-head">{tr.table.margin}</span>
              <span className={`tabular ${signClass(analysis.margin_pct)}`}>
                {formatPercent(analysis.margin_pct)}
              </span>
            </div>
            <div className="flex items-center justify-between text-cell">
              <span className="col-head">{tr.detail.commission}</span>
              <span className="tabular">
                {analysis.commission_rate === null
                  ? tr.commissionSource.unknown
                  : formatPercent(toNumber(analysis.commission_rate) * 100)}
              </span>
            </div>
            {analysis.warnings.length > 0 ? (
              <ul className="flex flex-col gap-1 border-t border-hairline pt-2 text-helper text-estimated-text">
                {analysis.warnings.map((code) => (
                  <li key={code}>{WARNING_LABELS[code] ?? code}</li>
                ))}
              </ul>
            ) : null}
            <div className="border-t border-hairline pt-3">
              <Waterfall
                steps={analysis.waterfall.map((step) => ({
                  key: String(step.key),
                  amount: String(step.amount),
                }))}
              />
            </div>
          </>
        ) : (
          <p className="py-10 text-center text-cell text-ink-muted">{tr.drafts.emptyCard}</p>
        )}
      </div>
    </div>
  );
}

function Field({
  name,
  label,
  type = "text",
  step,
  required,
  placeholder,
}: {
  name: string;
  label: string;
  type?: string;
  step?: string;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="col-head">
        {label}
        {required ? " *" : ""}
      </span>
      <input
        name={name}
        type={type}
        step={step}
        required={required}
        placeholder={placeholder}
        className="control tabular"
      />
    </label>
  );
}

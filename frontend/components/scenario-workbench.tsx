"use client";

/**
 * Senaryolar ekranı (spec §12A.4, tasarım brief'i ekran 6).
 *
 * Ürün seç → senaryo kur → hesapla/kaydet → hedef marj çözücü. Kayıtlı senaryolardan
 * en fazla 3'ü seçilip yan yana karşılaştırılır.
 */

import { useState, useTransition } from "react";

import {
  compareAction,
  evaluateAction,
  saveAction,
  type ScenarioState,
  targetMarginAction,
} from "@/app/[brand]/scenarios/actions";
import type { PriceRow, ScenarioResult } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatMoney, formatPercent, signClass, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

const MAX_COMPARE = 3;

export function ScenarioWorkbench({
  brand,
  products,
  saved,
}: {
  brand: BrandSlug;
  products: PriceRow[];
  saved: ScenarioResult[];
}) {
  const [state, setState] = useState<ScenarioState>({ status: "idle" });
  const [selected, setSelected] = useState<string[]>([]);
  const [pending, startTransition] = useTransition();

  const run = (form: HTMLFormElement, action: typeof evaluateAction) => {
    const formData = new FormData(form);
    formData.set("brand", brand);
    startTransition(async () => {
      setState(await action({ status: "idle" }, formData));
    });
  };

  const toggle = (scenarioId: string) => {
    setSelected((current) =>
      current.includes(scenarioId)
        ? current.filter((item) => item !== scenarioId)
        : current.length >= MAX_COMPARE
          ? current
          : [...current, scenarioId],
    );
  };

  const compare = () => {
    startTransition(async () => {
      setState(await compareAction(brand, selected));
    });
  };

  const results = state.results ?? [];
  const target = state.target;

  return (
    <div className="flex flex-col gap-6">
      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          run(event.currentTarget, evaluateAction);
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs sm:col-span-2">
            <span className="text-ink-faint">{tr.scenarios.product} *</span>
            <select
              name="product_id"
              required
              className="rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm"
            >
              {products.map((product) => (
                <option key={product.product_id} value={product.product_id}>
                  {product.sku} — {product.name}
                </option>
              ))}
            </select>
          </label>
          <Field name="name" label={tr.scenarios.name} defaultValue="Senaryo 1" />
          <Field
            name="satis_fiyati"
            label={tr.scenarios.price}
            type="number"
            step="0.01"
            required
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Field
            name="kampanya_indirim_pct"
            label={tr.scenarios.discount}
            type="number"
            step="0.1"
          />
          <Field
            name="kampanya_satici_pay_pct"
            label={tr.scenarios.sellerShare}
            type="number"
            step="0.1"
          />
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-ink-faint">{tr.scenarios.shipping}</span>
            <select
              name="kargo_kim_oder"
              defaultValue="satici"
              className="rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm"
            >
              <option value="satici">{tr.scenarios.payer.satici}</option>
              <option value="alici">{tr.scenarios.payer.alici}</option>
              <option value="platform">{tr.scenarios.payer.platform}</option>
            </select>
          </label>
          <Field name="kargo_tahmini" label={tr.drafts.cargo} type="number" step="0.01" />
          <Field
            name="adet_varsayimi"
            label={tr.scenarios.quantity}
            type="number"
            step="1"
            defaultValue="1"
          />
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <button
            type="submit"
            disabled={pending}
            className="rounded-card border border-hairline px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-canvas"
          >
            {tr.scenarios.evaluate}
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={(event) => {
              const form = event.currentTarget.form;
              if (form) run(form, saveAction);
            }}
            className="rounded-card border border-ink bg-ink px-3 py-1.5 text-sm text-surface disabled:opacity-40"
          >
            {tr.scenarios.save}
          </button>
          <span className="ml-auto flex items-end gap-2">
            <Field
              name="hedef_marj_pct"
              label={tr.scenarios.targetMargin}
              type="number"
              step="0.1"
              defaultValue="20"
            />
            <button
              type="button"
              disabled={pending}
              onClick={(event) => {
                const form = event.currentTarget.form;
                if (form) run(form, targetMarginAction);
              }}
              className="rounded-card border border-hairline px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-canvas"
            >
              {tr.scenarios.solve}
            </button>
          </span>
        </div>
        {state.status === "error" ? (
          <p className="text-sm text-negative">{state.message}</p>
        ) : null}
        {state.status === "saved" ? (
          <p className="text-sm text-positive">{tr.scenarios.saved}</p>
        ) : null}
      </form>

      {target ? (
        <div className="card flex flex-col gap-2 p-4">
          <span className="text-xs uppercase tracking-wide text-ink-faint">
            {tr.scenarios.solverTitle}
          </span>
          {target.reachable && target.price ? (
            <>
              <p className="text-sm">
                {tr.scenarios.solverAnswer
                  .replace("{marj}", formatPercent(target.target_margin_pct))
                  .replace("{fiyat}", formatMoney(target.price))}
              </p>
              {target.result ? (
                <p className="text-xs text-ink-faint">
                  {tr.scenarios.solverCheck} {formatPercent(target.result.marj_pct)}
                </p>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-negative">{target.message}</p>
          )}
        </div>
      ) : null}

      {results.length > 0 ? <ResultTable results={results} /> : null}

      {saved.length > 0 ? (
        <div className="flex flex-col gap-2 border-t border-hairline pt-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium">{tr.scenarios.savedTitle}</span>
            <span className="text-xs text-ink-faint">{tr.scenarios.compareHint}</span>
            <button
              type="button"
              onClick={compare}
              disabled={pending || selected.length < 2}
              className="ml-auto rounded-card border border-hairline px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-canvas"
            >
              {tr.scenarios.compare} ({selected.length}/{MAX_COMPARE})
            </button>
          </div>
          <ul className="flex flex-col">
            {saved.map((scenario) => (
              <li
                key={scenario.scenario_id ?? scenario.name}
                className="flex items-center gap-3 border-b border-hairline py-2 text-sm"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(String(scenario.scenario_id))}
                  onChange={() => toggle(String(scenario.scenario_id))}
                  aria-label={scenario.name}
                />
                <span className="font-medium">{scenario.name}</span>
                <span className="font-mono text-xs text-ink-faint">{scenario.sku}</span>
                <span className="ml-auto tabular">{formatMoney(scenario.satis_fiyati)}</span>
                <span className={`w-24 text-right tabular ${signClass(scenario.birim_kar)}`}>
                  {formatMoney(scenario.birim_kar)}
                </span>
                <span className={`w-16 text-right tabular ${signClass(scenario.marj_pct)}`}>
                  {formatPercent(scenario.marj_pct)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function ResultTable({ results }: { results: ScenarioResult[] }) {
  const rows: { label: string; value: (result: ScenarioResult) => string; tone?: boolean }[] = [
    { label: tr.scenarios.price, value: (r) => formatMoney(r.satis_fiyati) },
    { label: tr.scenarios.customerPays, value: (r) => formatMoney(r.musteri_odedigi) },
    {
      label: tr.scenarios.commissionRate,
      value: (r) =>
        r.commission_rate === null
          ? tr.commissionSource.unknown
          : formatPercent(toNumber(r.commission_rate) * 100),
    },
    { label: tr.scenarios.cargo, value: (r) => formatMoney(r.cargo_cost) },
    { label: tr.scenarios.unitProfit, value: (r) => formatMoney(r.birim_kar), tone: true },
    { label: tr.table.margin, value: (r) => formatPercent(r.marj_pct), tone: true },
    { label: tr.scenarios.quantity, value: (r) => String(r.adet) },
    { label: tr.scenarios.totalProfit, value: (r) => formatMoney(r.toplam_kar), tone: true },
    {
      label: tr.scenarios.breakEven,
      value: (r) => (r.basabas_fiyat === null ? "—" : formatMoney(r.basabas_fiyat)),
    },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-hairline text-xs font-medium text-ink-faint">
            <th className="px-3 py-2 text-left">{tr.scenarios.metric}</th>
            {results.map((result, index) => (
              <th key={`${result.name}-${index}`} className="px-3 py-2 text-right">
                {result.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-hairline">
              <td className="px-3 py-1.5 text-ink-faint">{row.label}</td>
              {results.map((result, index) => (
                <td
                  key={`${result.name}-${index}`}
                  className={`px-3 py-1.5 text-right tabular ${
                    row.tone ? signClass(row.label === tr.table.margin ? result.marj_pct : result.birim_kar) : ""
                  }`}
                >
                  {row.value(result)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Field({
  name,
  label,
  type = "text",
  step,
  required,
  defaultValue,
}: {
  name: string;
  label: string;
  type?: string;
  step?: string;
  required?: boolean;
  defaultValue?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="text-ink-faint">
        {label}
        {required ? " *" : ""}
      </span>
      <input
        name={name}
        type={type}
        step={step}
        required={required}
        defaultValue={defaultValue}
        className="w-full rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm tabular"
      />
    </label>
  );
}

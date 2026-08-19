"use client";

/**
 * Tarife Excel yükleme (spec §12B.2, tasarım brief'i ekran 10).
 *
 * Önce dry-run: parser hangi sütunu ne olarak okuduğunu söyler ve tarifenin kâra
 * etkisini gösterir. Kullanıcı onaylamadan hiçbir kayıt yazılmaz.
 */

import { useState, useTransition } from "react";

import {
  applyTariffUpload,
  previewTariffUpload,
  type UploadState,
} from "@/app/[brand]/tariffs/actions";
import type { BrandSlug } from "@/lib/brands";
import { formatMoney, formatPercent, signClass, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

export function TariffUpload({ brand }: { brand: BrandSlug }) {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const send = (form: HTMLFormElement, apply: boolean) => {
    const formData = new FormData(form);
    formData.set("brand", brand);
    if (file) formData.set("file", file, file.name);
    startTransition(async () => {
      const action = apply ? applyTariffUpload : previewTariffUpload;
      setState(await action({ status: "idle" }, formData));
    });
  };

  const result = state.result;
  const mapping = (result?.mapping ?? {}) as Record<string, unknown>;

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        send(event.currentTarget, false);
      }}
    >
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex h-[34px] cursor-pointer items-center rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas">
          <input
            type="file"
            name="file"
            accept=".xlsx"
            className="hidden"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setState({ status: "idle" });
            }}
          />
          {tr.pricelist.chooseFile}
        </label>
        <span className="text-helper text-ink-muted">{file ? file.name : tr.pricelist.noFile}</span>
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.tariffs.validFromLabel} *</span>
          <input
            name="valid_from"
            type="date"
            required
            className="control tabular"
          />
        </label>
        <button
          type="submit"
          disabled={!file || pending}
          className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
        >
          {pending ? tr.pricelist.checking : tr.pricelist.preview}
        </button>
      </div>

      {state.status === "error" ? (
        <p className="text-cell text-negative">{state.message}</p>
      ) : null}

      {result ? (
        <div className="flex flex-col gap-3 border-t border-hairline pt-3">
          <div className="rounded-card border border-hairline bg-canvas p-3 text-helper">
            <p className="mb-1 font-medium">{tr.tariffs.readAs}</p>
            <ul className="flex flex-col gap-0.5 text-ink-muted">
              <li>
                {tr.tariffs.headerRow}: {String(mapping.header_row ?? "—")}
              </li>
              <li>
                {tr.tariffs.rateColumn}: <strong>{String(mapping.rate_header ?? "—")}</strong>
              </li>
              <li>
                {tr.tariffs.categoryColumns}:{" "}
                <strong>
                  {Array.isArray(mapping.category_headers)
                    ? (mapping.category_headers as string[]).join(" › ")
                    : "—"}
                </strong>
              </li>
              {mapping.code_header ? (
                <li>
                  {tr.tariffs.codeColumn}: {String(mapping.code_header)}
                </li>
              ) : null}
              {mapping.campaign_header ? (
                <li>
                  {tr.tariffs.campaignColumn}: {String(mapping.campaign_header)}
                </li>
              ) : null}
            </ul>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-cell">
            <span>
              {tr.tariffs.matched}: <span className="tabular">{result.matched}</span>
            </span>
            <span>
              {tr.tariffs.changedRows}: <span className="tabular">{result.changed}</span>
            </span>
            <span className="col-head">
              {tr.tariffs.unchangedRows}: <span className="tabular">{result.unchanged}</span>
            </span>
            <span className="text-positive">
              {tr.tariffs.newRows}: <span className="tabular">{result.new_categories}</span>
            </span>
            <span className={result.errors.length > 0 ? "text-negative" : "text-ink-muted"}>
              {tr.pricelist.errors}: <span className="tabular">{result.errors.length}</span>
            </span>
            <span className="ml-auto flex items-center gap-3">
              <span className="text-helper text-ink-muted">{tr.tariffs.monthlyImpact}</span>
              <span
                className={`tabular text-title font-medium ${signClass(result.monthly_profit_impact)}`}
              >
                {formatMoney(result.monthly_profit_impact)}
              </span>
            </span>
          </div>

          {state.status === "preview" ? (
            <div className="flex items-center gap-3">
              <button
                type="button"
                disabled={pending || result.matched === 0}
                onClick={(event) => {
                  const form = event.currentTarget.form;
                  if (form) send(form, true);
                }}
                className="h-[34px] rounded-control border border-ink bg-ink px-3 text-cell font-medium text-white hover:bg-ink-secondary disabled:opacity-40"
              >
                {tr.tariffs.confirmUpload}
              </button>
              <span className="text-helper text-ink-muted">{tr.pricelist.dryRunNote}</span>
            </div>
          ) : (
            <p className="text-cell text-positive-text">
              {tr.tariffs.uploaded} ({result.written})
            </p>
          )}

          {result.changes.length > 0 ? (
            <div className="max-h-56 overflow-auto">
              <table className="w-full border-collapse text-cell">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-hairline text-column uppercase text-ink-muted">
                    <th className="px-3 py-2 text-left">{tr.table.category}</th>
                    <th className="px-3 py-2 text-right">{tr.tariffs.oldRate}</th>
                    <th className="px-3 py-2 text-right">{tr.tariffs.newRate}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.changes.map((change, index) => {
                    const row = change as Record<string, unknown>;
                    return (
                      <tr key={`${String(row.category)}-${index}`} className="border-b border-hairline">
                        <td className="px-3 py-1.5">{String(row.category)}</td>
                        <td className="px-3 py-1.5 text-right tabular">
                          {formatPercent(toNumber(String(row.old_rate)) * 100)}
                        </td>
                        <td className="px-3 py-1.5 text-right tabular">
                          {formatPercent(toNumber(String(row.new_rate)) * 100)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}

          {result.unmatched.length > 0 ? (
            <details className="text-helper text-ink-muted">
              <summary className="cursor-pointer">
                {tr.tariffs.unmatchedRows}: {result.unmatched.length}
              </summary>
              <p className="mt-1 text-ink-muted">{tr.tariffs.unmatchedNote}</p>
              <p className="mt-1">{result.unmatched.join(" · ")}</p>
            </details>
          ) : null}

          {result.errors.length > 0 ? (
            <ul className="flex flex-col gap-1 text-negative">
              {result.errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </form>
  );
}

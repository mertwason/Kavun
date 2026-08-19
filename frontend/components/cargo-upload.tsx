"use client";

/**
 * Kargo faturası yükleme (spec §5.3, §6.2).
 *
 * Önce `dry_run` önizleme: kaç gönderi kesinleşecek, kaçı eşleşmedi, tahminle fark ne.
 * Kullanıcı onaylamadan hiçbir maliyet kesinleşmez — kesinleşme kârı revize eder ve
 * revizyonlar `profit_revisions`'a append-only loglanır.
 */

import { useState, useTransition } from "react";

import {
  applyCargoUpload,
  type CargoUploadState,
  previewCargoUpload,
} from "@/app/[brand]/cargo/actions";
import type { BrandSlug } from "@/lib/brands";
import { formatMoney, signClass, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

const ACTION_LABELS: Record<string, string> = tr.cargo.actions;

const ACTION_TONE: Record<string, string> = {
  kesinlesti: "text-positive",
  zaten_kesin: "text-ink-muted",
  eslesmedi: "text-negative",
  hata: "text-negative",
};

const FIELD = "control";

export function CargoUpload({ brand }: { brand: BrandSlug }) {
  const [file, setFile] = useState<File | null>(null);
  const [invoiceNo, setInvoiceNo] = useState("");
  const [period, setPeriod] = useState("");
  const [state, setState] = useState<CargoUploadState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const send = (apply: boolean) => {
    if (!file) {
      setState({ status: "error", message: tr.cargo.noFile });
      return;
    }
    const formData = new FormData();
    formData.append("brand", brand);
    formData.append("file", file, file.name);
    formData.append("invoice_no", invoiceNo);
    formData.append("period", period);
    startTransition(async () => {
      const action = apply ? applyCargoUpload : previewCargoUpload;
      setState(await action({ status: "idle" }, formData));
    });
  };

  const result = state.result;
  // Kesinleşen satırlar beklenen sonuçtur; dikkat isteyenler listelenir.
  const notable = result?.results.filter((row) => row.action !== "kesinlesti") ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <a
          href={`/${brand}/cargo/template`}
          className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
        >
          {tr.cargo.downloadTemplate}
        </a>
        <label className="flex h-[34px] cursor-pointer items-center rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas">
          <input
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setState({ status: "idle" });
            }}
          />
          {tr.cargo.chooseFile}
        </label>
        <span className="text-helper text-ink-muted">{file ? file.name : tr.cargo.noFile}</span>
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.cargo.invoiceNo} *</span>
          <input
            name="invoice_no"
            type="text"
            value={invoiceNo}
            onChange={(event) => setInvoiceNo(event.target.value)}
            className={`${FIELD} w-40`}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.cargo.period} *</span>
          <input
            name="period"
            type="month"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
            className={`${FIELD} w-36`}
          />
        </label>
        <button
          type="button"
          onClick={() => send(false)}
          disabled={!file || pending}
          className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
        >
          {pending ? tr.cargo.checking : tr.cargo.preview}
        </button>
        {state.status === "preview" ? (
          <button
            type="button"
            onClick={() => send(true)}
            disabled={pending}
            className="h-[34px] rounded-control border border-ink bg-ink px-3 text-cell font-medium text-white hover:bg-ink-secondary disabled:opacity-40"
          >
            {tr.cargo.apply}
          </button>
        ) : null}
      </div>

      {state.status === "error" ? <p className="text-cell text-negative">{state.message}</p> : null}

      {result ? (
        <div className="flex flex-col gap-3 border-t border-hairline pt-3">
          <div className="flex flex-wrap items-baseline gap-6 text-cell">
            <Stat label={tr.cargo.rows} value={String(result.rows)} />
            <Stat label={tr.cargo.matched} value={String(result.kesinlesti)} tone="text-positive" />
            <Stat label={tr.cargo.already} value={String(result.zaten_kesin)} />
            <Stat
              label={tr.cargo.unmatched}
              value={String(result.eslesmedi)}
              tone={result.eslesmedi > 0 ? "text-negative" : undefined}
            />
            <Stat
              label={tr.cargo.errors}
              value={String(result.hata)}
              tone={result.hata > 0 ? "text-negative" : undefined}
            />
            <Stat label={tr.cargo.total} value={formatMoney(result.total_amount)} />
            <Stat
              label={tr.cargo.delta}
              value={formatMoney(result.delta)}
              tone={signClass(-toNumber(result.delta))}
            />
          </div>
          <p className="text-helper text-ink-muted">
            {state.status === "applied" ? tr.cargo.appliedNote : tr.cargo.previewNote} ·{" "}
            {tr.cargo.deltaHint}
          </p>

          {notable.length > 0 ? (
            <div className="max-h-64 overflow-auto">
              <table className="w-full border-collapse text-cell">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-hairline text-column uppercase text-ink-muted">
                    <th className="px-3 py-2 text-left">{tr.cargo.reference}</th>
                    <th className="px-3 py-2 text-left">{tr.table.status}</th>
                    <th className="px-3 py-2 text-right">{tr.cargo.newAmount}</th>
                    <th className="px-3 py-2 text-left">{tr.table.detail}</th>
                  </tr>
                </thead>
                <tbody>
                  {notable.map((row) => (
                    <tr key={`${row.row_no}-${row.reference}`} className="border-b border-hairline">
                      <td className="px-3 py-1.5 font-mono text-helper text-ink-muted">
                        {row.reference}
                      </td>
                      <td className={`px-3 py-1.5 ${ACTION_TONE[row.action] ?? ""}`}>
                        {ACTION_LABELS[row.action] ?? row.action}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular">{formatMoney(row.amount)}</td>
                      <td className="px-3 py-1.5 text-helper text-ink-muted">{row.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <span className="flex flex-col">
      <span className="text-helper text-ink-muted">{label}</span>
      <span className={`text-kpiSm ${tone ?? ""}`}>{value}</span>
    </span>
  );
}

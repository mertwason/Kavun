"use client";

/** Fatura PDF yükleme (spec §12C.3) — ayrıştırma sonucu stoka YAZILMAZ. */

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { type InvoiceUploadState, uploadAction } from "@/app/[brand]/invoices/actions";
import type { BrandSlug } from "@/lib/brands";
import { formatMoney } from "@/lib/format";
import tr from "@/locales/tr.json";

export function InvoiceUpload({
  brand,
  suppliers,
}: {
  brand: BrandSlug;
  suppliers?: { id: string; name: string }[];
}) {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<InvoiceUploadState>({ status: "idle" });
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        formData.set("brand", brand);
        if (file) formData.set("file", file, file.name);
        startTransition(async () => {
          const result = await uploadAction({ status: "idle" }, formData);
          setState(result);
          if (result.status === "uploaded" && result.result) {
            router.push(`/${brand}/invoices/${result.result.invoice_id}`);
          }
        });
      }}
    >
      <div className="flex flex-wrap items-end gap-3">
        <label className="cursor-pointer rounded-card border border-hairline px-3 py-1.5 text-sm hover:bg-canvas">
          <input
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setState({ status: "idle" });
            }}
          />
          {tr.invoices.choosePdf}
        </label>
        <span className="text-xs text-ink-faint">{file ? file.name : tr.pricelist.noFile}</span>

        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.invoices.supplier} *</span>
          {suppliers && suppliers.length > 0 ? (
            <select
              name="supplier_id"
              required
              className="rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm"
            >
              {suppliers.map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name}
                </option>
              ))}
            </select>
          ) : (
            <input
              name="supplier_id"
              required
              placeholder={tr.invoices.supplierIdHint}
              className="w-72 rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm"
            />
          )}
        </label>

        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.invoices.invoiceNo} *</span>
          <input
            name="invoice_no"
            required
            className="w-44 rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.invoices.invoiceDate} *</span>
          <input
            name="invoice_date"
            type="date"
            required
            className="rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm tabular"
          />
        </label>

        <button
          type="submit"
          disabled={!file || pending}
          className="rounded-card border border-hairline px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-canvas"
        >
          {pending ? tr.pricelist.checking : tr.invoices.parse}
        </button>
      </div>

      {state.status === "error" ? (
        <p className="text-sm text-negative">{state.message}</p>
      ) : null}

      {state.status === "uploaded" && state.result ? (
        <p className="text-sm">
          {tr.invoices.parsed}: {state.result.lines} · {tr.invoices.unmatchedCount}:{" "}
          {state.result.unmatched} ·{" "}
          <span className={state.result.totals_ok ? "text-positive" : "text-negative"}>
            {tr.invoices.totalCheck}: {formatMoney(state.result.lines_total)}
          </span>
        </p>
      ) : null}
    </form>
  );
}

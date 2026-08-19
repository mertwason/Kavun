"use client";

/**
 * Fatura PDF yükleme — handoff `Fatura Yukleme.dc.html` boş durumu (spec §12C.3).
 *
 * Dosya seçilmeden önce ekranda yalnızca kesikli çerçeveli bırakma alanı vardır; künye
 * alanları (tedarikçi / fatura no / tarih) dosya geldikten sonra açılır — boş formda
 * kullanıcıya doldurulacak dört kutu göstermek yerine tek bir eylem bırakılır.
 *
 * Ayrıştırma sonucu stoka YAZILMAZ: satırlar onay ekranına düşer.
 */

import { FileText, Upload, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";

import { type InvoiceUploadState, uploadAction } from "@/app/[brand]/invoices/actions";
import { BRANDS, type BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

/** Backend `MAX_UPLOAD_BYTES` ile birebir aynı olmalı (backend/app/api/invoices.py). */
const MAX_BYTES = 20 * 1024 * 1024;

export function InvoiceUpload({
  brand,
  suppliers,
}: {
  brand: BrandSlug;
  suppliers?: { id: string; name: string }[];
}) {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [state, setState] = useState<InvoiceUploadState>({ status: "idle" });
  const [pending, startTransition] = useTransition();
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const accent = BRANDS[brand].accent;

  const accept = (picked: File | null | undefined) => {
    if (!picked) return;
    if (!picked.name.toLowerCase().endsWith(".pdf")) {
      setFile(null);
      setState({ status: "error", message: tr.invoices.onlyPdf });
      return;
    }
    if (picked.size > MAX_BYTES) {
      setFile(null);
      setState({ status: "error", message: tr.invoices.tooLarge });
      return;
    }
    setFile(picked);
    setState({ status: "idle" });
  };

  return (
    <form
      className="flex flex-col gap-4"
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
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        onChange={(event) => accept(event.target.files?.[0])}
      />

      {file ? (
        <div className="flex items-center gap-3 rounded-card border border-hairline bg-canvas px-4 py-3">
          <FileText className="h-4 w-4 shrink-0 text-ink-secondary" aria-hidden />
          <span className="min-w-0 flex-1 truncate text-cell font-medium">{file.name}</span>
          <span className="shrink-0 text-helper text-ink-muted tabular-nums">
            {(file.size / 1024 / 1024).toFixed(1)} MB
          </span>
          <button
            type="button"
            onClick={() => {
              setFile(null);
              setState({ status: "idle" });
              if (inputRef.current) inputRef.current.value = "";
            }}
            aria-label={tr.invoices.removeFile}
            className="shrink-0 rounded-control p-1 text-ink-muted hover:bg-hairline hover:text-ink"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            accept(event.dataTransfer.files?.[0]);
          }}
          className={`flex flex-col items-center gap-2 rounded-card border border-dashed px-6 py-10 text-center transition-colors ${
            dragging ? "border-ink-faint bg-canvas" : "border-hairline bg-surface hover:bg-canvas"
          }`}
        >
          <Upload className="h-5 w-5 text-ink-faint" aria-hidden />
          <span className="text-cell font-medium">{tr.invoices.dropTitle}</span>
          <span className="text-helper text-ink-body">{tr.invoices.dropHint}</span>
          <span className="mt-1 text-micro text-ink-muted">{tr.invoices.dropSupport}</span>
        </button>
      )}

      {file ? (
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="col-head">{tr.invoices.supplier}</span>
            {suppliers && suppliers.length > 0 ? (
              <select name="supplier_id" required className="control">
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
                className="control w-72"
              />
            )}
          </label>

          <label className="flex flex-col gap-1">
            <span className="col-head">{tr.invoices.invoiceNo}</span>
            <input name="invoice_no" required className="control w-44" />
          </label>

          <label className="flex flex-col gap-1">
            <span className="col-head">{tr.invoices.invoiceDate}</span>
            <input name="invoice_date" type="date" required className="control" />
          </label>

          <button
            type="submit"
            disabled={pending}
            className="h-[34px] rounded-control px-3.5 text-cell font-medium text-white disabled:cursor-not-allowed disabled:bg-hairline disabled:text-ink-muted"
            style={pending ? undefined : { backgroundColor: accent }}
          >
            {pending ? tr.pricelist.checking : tr.invoices.parse}
          </button>
        </div>
      ) : null}

      {state.status === "error" ? (
        <p className="text-cell text-negative">{state.message}</p>
      ) : null}
    </form>
  );
}

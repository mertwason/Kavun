"use client";

/**
 * D2B satış dosyası yükleme (spec §12C.9).
 *
 * Önce `dry_run` önizleme: kaç sipariş/kalem yazılacak, hangi satırlar reddedildi.
 * Kullanıcı onaylamadan HİÇBİR sipariş yazılmaz (KVN-10 disiplini).
 */

import { useState, useTransition } from "react";

import { applyD2bUpload, type D2bUploadState, previewD2bUpload } from "@/app/[brand]/d2b/actions";
import type { BrandSlug } from "@/lib/brands";
import { formatMoney } from "@/lib/format";
import tr from "@/locales/tr.json";

export function D2bUpload({ brand }: { brand: BrandSlug }) {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<D2bUploadState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const send = (apply: boolean) => {
    if (!file) {
      setState({ status: "error", message: tr.d2b.noFile });
      return;
    }
    const formData = new FormData();
    formData.append("brand", brand);
    formData.append("file", file, file.name);
    startTransition(async () => {
      const action = apply ? applyD2bUpload : previewD2bUpload;
      setState(await action({ status: "idle" }, formData));
    });
  };

  const result = state.result;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <a
          href={`/${brand}/d2b/template`}
          className="rounded-card border border-hairline px-3 py-1.5 text-sm hover:bg-canvas"
        >
          {tr.d2b.downloadTemplate}
        </a>
        <label className="cursor-pointer rounded-card border border-hairline px-3 py-1.5 text-sm hover:bg-canvas">
          <input
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setState({ status: "idle" });
            }}
          />
          {tr.d2b.chooseFile}
        </label>
        <span className="text-xs text-ink-faint">{file ? file.name : tr.d2b.noFile}</span>
        <button
          type="button"
          onClick={() => send(false)}
          disabled={!file || pending}
          className="rounded-card border border-hairline px-3 py-1.5 text-sm hover:bg-canvas disabled:opacity-40"
        >
          {pending ? tr.d2b.checking : tr.d2b.preview}
        </button>
        {state.status === "preview" ? (
          <button
            type="button"
            onClick={() => send(true)}
            disabled={pending}
            className="rounded-card border border-ink px-3 py-1.5 text-sm hover:bg-canvas disabled:opacity-40"
          >
            {tr.d2b.apply}
          </button>
        ) : null}
      </div>

      {state.status === "error" ? <p className="text-sm text-negative">{state.message}</p> : null}

      {result ? (
        <div className="flex flex-col gap-3 border-t border-hairline pt-3">
          <div className="flex flex-wrap items-baseline gap-6 text-sm">
            <Stat label={tr.d2b.rows} value={String(result.rows)} />
            <Stat label={tr.d2b.orders} value={String(result.orders)} />
            <Stat label={tr.d2b.lines} value={String(result.lines)} />
            <Stat label={tr.d2b.customers} value={String(result.customers)} />
            <Stat label={tr.d2b.skipped} value={String(result.skipped)} />
            <Stat label={tr.d2b.grossTotal} value={formatMoney(result.gross_total)} />
          </div>

          <p className="text-xs text-ink-faint">
            {state.status === "applied" ? tr.d2b.appliedNote : tr.d2b.previewNote}
          </p>

          {result.errors.length > 0 ? (
            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium text-negative">{tr.d2b.errors}</span>
              {result.errors.map((error) => (
                <span key={`${error.row_no}-${error.sku}`} className="text-xs text-ink-muted">
                  {error.row_no}. satır · {error.sku || "—"} · {error.reason}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex flex-col">
      <span className="text-xs text-ink-faint">{label}</span>
      <span className="tabular text-lg">{value}</span>
    </span>
  );
}

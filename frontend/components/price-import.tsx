"use client";

/**
 * Excel yükleme + diff önizleme (tasarım brief'i, kalıp 5).
 *
 * Önce `dry_run` ile önizleme: yeşil (yeni), mavi (güncelleme), kırmızı (hata) satır
 * grupları. Kullanıcı onaylamadan HİÇBİR ŞEY yazılmaz.
 */

import { useState, useTransition } from "react";

import { applyImport, previewImport, type UploadState } from "@/app/[brand]/products/actions";
import type { BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

const ACTION_TONE: Record<string, string> = {
  yeni: "text-positive",
  guncelleme: "text-ink",
  hata: "text-negative",
  degisiklik_yok: "text-ink-faint",
};

const ACTION_LABEL: Record<string, string> = tr.pricelist.actions;

export function PriceImport({ brand }: { brand: BrandSlug }) {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<UploadState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const send = (apply: boolean) => {
    if (!file) {
      setState({ status: "error", message: tr.pricelist.noFile });
      return;
    }
    const formData = new FormData();
    formData.append("brand", brand);
    formData.append("file", file, file.name);
    startTransition(async () => {
      const action = apply ? applyImport : previewImport;
      setState(await action({ status: "idle" }, formData));
    });
  };

  const summary = state.summary;
  const rows = summary?.rows.filter((row) => row.action !== "degisiklik_yok") ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
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
          {tr.pricelist.chooseFile}
        </label>
        <span className="text-xs text-ink-faint">{file ? file.name : tr.pricelist.noFile}</span>
        <button
          type="button"
          onClick={() => send(false)}
          disabled={!file || pending}
          className="rounded-card border border-hairline px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-canvas"
        >
          {pending && state.status === "idle" ? tr.pricelist.checking : tr.pricelist.preview}
        </button>
      </div>

      {state.status === "error" ? (
        <p className="text-sm text-negative">{state.message}</p>
      ) : null}

      {summary ? (
        <div className="flex flex-col gap-3 border-t border-hairline pt-3">
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <span className="text-positive">
              {tr.pricelist.new}: <span className="tabular">{summary.yeni}</span>
            </span>
            <span>
              {tr.pricelist.updated}: <span className="tabular">{summary.guncelleme}</span>
            </span>
            <span className="text-ink-faint">
              {tr.pricelist.unchanged}: <span className="tabular">{summary.degisiklik_yok}</span>
            </span>
            <span className={summary.hata > 0 ? "text-negative" : "text-ink-faint"}>
              {tr.pricelist.errors}: <span className="tabular">{summary.hata}</span>
            </span>
            {state.status === "preview" ? (
              <button
                type="button"
                onClick={() => send(true)}
                disabled={pending || summary.yeni + summary.guncelleme === 0}
                className="ml-auto rounded-card border border-ink bg-ink px-3 py-1.5 text-sm text-surface disabled:opacity-40"
              >
                {pending ? tr.pricelist.applying : tr.pricelist.apply}
              </button>
            ) : (
              <span className="ml-auto text-positive">{tr.pricelist.applied}</span>
            )}
          </div>

          {state.status === "preview" ? (
            <p className="text-xs text-ink-faint">{tr.pricelist.dryRunNote}</p>
          ) : null}

          {rows.length > 0 ? (
            <div className="max-h-72 overflow-auto">
              <table className="w-full border-collapse text-sm">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-hairline text-xs font-medium text-ink-faint">
                    <th className="px-3 py-2 text-left">{tr.pricelist.row}</th>
                    <th className="px-3 py-2 text-left">{tr.table.sku}</th>
                    <th className="px-3 py-2 text-left">{tr.pricelist.channel}</th>
                    <th className="px-3 py-2 text-left">{tr.pricelist.change}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={`${row.row_no}-${row.channel}`}
                      className={`border-b border-hairline ${
                        row.action === "hata" ? "bg-negative/[0.04]" : ""
                      } ${row.action === "yeni" ? "bg-positive/[0.04]" : ""}`}
                    >
                      <td className="px-3 py-1.5 tabular text-ink-faint">{row.row_no}</td>
                      <td className="px-3 py-1.5 font-mono text-xs">{row.sku || "—"}</td>
                      <td className="px-3 py-1.5 text-ink-muted">{row.channel || "—"}</td>
                      <td className={`px-3 py-1.5 ${ACTION_TONE[row.action] ?? ""}`}>
                        <span className="mr-2 text-xs uppercase tracking-wide">
                          {ACTION_LABEL[row.action] ?? row.action}
                        </span>
                        {row.message ||
                          Object.entries(row.changes)
                            .map(([key, value]) => `${key}: ${value}`)
                            .join(" · ")}
                      </td>
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

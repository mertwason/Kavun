"use client";

/**
 * Excel yükleme + diff önizleme — handoff `Urun Calisma Alani.dc.html` (spec §12A.6).
 *
 * Önce `dry_run` önizleme, sonra onay: kullanıcı onaylamadan HİÇBİR ŞEY yazılmaz.
 * Sonuç tek tabloda değil **üç grupta** gösterilir (yeni / güncelleme / hata) — kullanıcının
 * sorusu "kaç satır değişti" değil, "neyi kabul ediyorum". Her grup ilk beş satırı gösterir,
 * gerisi sayıyla özetlenir; onay butonunun yanındaki cümle kaç satırın gerçekten
 * uygulanacağını yazar.
 */

import { useState, useTransition } from "react";

import { applyImport, previewImport, type UploadState } from "@/app/[brand]/products/actions";
import type { BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

/** Grup başına gösterilen satır sayısı; gerisi "+ N satır daha" olarak özetlenir. */
const GROUP_PREVIEW = 5;

type Row = NonNullable<UploadState["summary"]>["rows"][number];

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
  const rows = summary?.rows ?? [];
  const applied = (summary?.yeni ?? 0) + (summary?.guncelleme ?? 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
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
          {tr.pricelist.chooseFile}
        </label>
        <span className="text-helper text-ink-muted">
          {file ? file.name : tr.pricelist.noFile}
        </span>
        <button
          type="button"
          onClick={() => send(false)}
          disabled={!file || pending}
          className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
        >
          {pending && state.status === "idle" ? tr.pricelist.checking : tr.pricelist.preview}
        </button>
      </div>

      {state.status === "error" ? <p className="text-cell text-negative">{state.message}</p> : null}

      {summary ? (
        <div className="flex flex-col gap-3 border-t border-hairline pt-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-cell font-medium">
              {file
                ? tr.pricelist.fileRead
                    .replace("{file}", file.name)
                    .replace("{count}", String(rows.length))
                : ""}
            </span>
            <div className="flex-1" />
            <Chip label={tr.pricelist.new} count={summary.yeni} tone="positive" />
            <Chip label={tr.pricelist.updated} count={summary.guncelleme} tone="info" />
            <Chip label={tr.pricelist.unchanged} count={summary.degisiklik_yok} tone="muted" />
            <Chip label={tr.pricelist.errors} count={summary.hata} tone="negative" />
          </div>

          <Group
            title={tr.pricelist.new}
            tone="positive"
            rows={rows.filter((row) => row.action === "yeni")}
          />
          <Group
            title={tr.pricelist.updated}
            tone="info"
            rows={rows.filter((row) => row.action === "guncelleme")}
          />
          <Group
            title={tr.pricelist.errors}
            tone="negative"
            rows={rows.filter((row) => row.action === "hata")}
          />

          <div className="flex flex-wrap items-center gap-3 border-t border-hairline pt-3">
            <span className="text-helper text-ink-body">
              {summary.hata > 0
                ? tr.pricelist.applyNote
                    .replace("{errors}", String(summary.hata))
                    .replace("{applied}", String(applied))
                : tr.pricelist.applyNoteClean.replace("{applied}", String(applied))}
            </span>
            <div className="flex-1" />
            {state.status === "preview" ? (
              <>
                <button
                  type="button"
                  onClick={() => {
                    setFile(null);
                    setState({ status: "idle" });
                  }}
                  className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
                >
                  {tr.pricelist.cancel}
                </button>
                <button
                  type="button"
                  onClick={() => send(true)}
                  disabled={pending || applied === 0}
                  className="h-[34px] rounded-control border border-ink bg-ink px-3 text-cell font-medium text-white hover:bg-ink-secondary disabled:opacity-40"
                >
                  {pending ? tr.pricelist.applying : tr.pricelist.apply}
                </button>
              </>
            ) : (
              <span className="badge border-positive-border bg-positive-tint text-positive-text">
                {tr.pricelist.applied}
              </span>
            )}
          </div>

          {state.status === "preview" ? (
            <p className="text-helper text-ink-muted">{tr.pricelist.dryRunNote}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

type Tone = "positive" | "info" | "negative" | "muted";

const CHIP_STYLE: Record<Tone, string> = {
  positive: "border-positive-border bg-positive-tint text-positive-text",
  info: "border-info-border bg-info-tint text-info",
  negative: "border-negative-border bg-negative-tint text-negative",
  muted: "border-hairline bg-canvas text-ink-muted",
};

function Chip({ label, count, tone }: { label: string; count: number; tone: Tone }) {
  return (
    <span className={`badge ${count === 0 ? CHIP_STYLE.muted : CHIP_STYLE[tone]}`}>
      {count} {label.toLocaleLowerCase("tr-TR")}
    </span>
  );
}

function Group({ title, tone, rows }: { title: string; tone: Tone; rows: Row[] }) {
  if (rows.length === 0) return null;
  const shown = rows.slice(0, GROUP_PREVIEW);
  const rest = rows.length - shown.length;

  return (
    <div className="flex flex-col gap-1.5">
      <span className="col-head">
        {title} · {rows.length}
      </span>
      <div className="overflow-hidden rounded-card border border-hairline">
        {shown.map((row) => (
          <div
            key={`${row.row_no}-${row.channel}-${row.action}`}
            className={`flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-hairline px-3 py-2 last:border-b-0 ${
              tone === "negative" ? "bg-negative-row" : "bg-surface"
            }`}
          >
            <span className="w-10 shrink-0 text-helper text-ink-muted">{row.row_no}</span>
            <span className="font-mono text-micro text-ink-secondary">{row.sku || "—"}</span>
            <span className="min-w-0 flex-1 text-cell">
              {row.message || describe(row)}
            </span>
          </div>
        ))}
        {rest > 0 ? (
          <div className="border-t border-hairline bg-canvas px-3 py-1.5 text-helper text-ink-muted">
            {tr.pricelist.moreRows.replace("{count}", String(rest))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/** Değişiklik satırını "alan: eski → yeni" biçiminde okunur hâle getirir. */
function describe(row: Row): string {
  const parts = Object.entries(row.changes).map(([key, value]) => `${key}: ${value}`);
  return parts.length > 0 ? parts.join(" · ") : (row.channel ?? "");
}

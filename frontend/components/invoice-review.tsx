"use client";

/**
 * Fatura onay ekranı — handoff `Fatura Yukleme.dc.html` (spec §12C.3).
 *
 * Split düzen: solda faturanın künyesi, sağda ayrıştırılan satırlar. Satır kartları üç
 * durumdan birinde olur — otomatik eşleşti (yeşil), öneri var (amber, onay ister),
 * eşleşmedi (gri, seçim ister). Altta **yapışkan doğrulama barı**: satır toplamı fatura
 * toplamıyla uyuşmuyorsa onay butonu kapalıdır.
 *
 * **Tasarımdan sapma:** handoff solda PDF önizlemesi gösteriyor. Kavun PDF'i saklamıyor —
 * yalnızca ayrıştırıp atıyor (spec §12C.3 dosya saklama demiyor). Var olmayan bir belgeyi
 * gri bloklarla taklit etmek yerine o alana faturanın gerçek künyesi konuldu. PDF saklamaya
 * karar verilirse önizleme buraya oturur.
 */

import { Check, CircleCheck, CircleDashed, TriangleAlert } from "lucide-react";
import { useState, useTransition } from "react";

import { confirmAction, matchLineAction } from "@/app/[brand]/invoices/actions";
import type { InvoiceDetail, InvoiceLine, PriceRow } from "@/lib/api";
import { BRANDS, type BrandSlug } from "@/lib/brands";
import {
  formatConfidence,
  formatDate,
  formatMoney,
  formatPercent,
  formatQuantity,
  toNumber,
} from "@/lib/format";
import tr from "@/locales/tr.json";

/** Fatura ile satır toplamı arasında kabul edilen fark (kuruş yuvarlaması). */
const TOLERANCE = 0.1;

export function InvoiceReview({
  brand,
  invoice,
  products,
}: {
  brand: BrandSlug;
  invoice: InvoiceDetail;
  products: PriceRow[];
}) {
  const [message, setMessage] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const accent = BRANDS[brand].accent;

  const confirmed = invoice.status === "confirmed";
  const linesTotal = invoice.lines.reduce(
    (sum, line) => sum + toNumber(line.unit_price_try) * toNumber(line.qty),
    0,
  );
  const declared = invoice.total === null ? null : toNumber(invoice.total);
  const difference = declared === null ? 0 : linesTotal - declared;
  const totalsOk = declared === null || Math.abs(difference) <= TOLERANCE;
  const unmatched = invoice.lines.filter((line) => line.product_id === null).length;
  const ready = totalsOk && unmatched === 0;

  const match = (lineId: string, productId: string) => {
    setMessage(null);
    startTransition(async () => {
      const result = await matchLineAction(brand, invoice.id, lineId, productId);
      if (result.status === "error") setMessage(result.message ?? null);
    });
  };

  const confirm = () => {
    setMessage(null);
    startTransition(async () => {
      const result = await confirmAction(brand, invoice.id);
      if (result.status === "error") setMessage(result.message ?? null);
    });
  };

  return (
    <div className="flex flex-col gap-4">
      {message ? <p className="text-cell text-negative">{message}</p> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,300px)_1fr]">
        <div className="card flex h-fit flex-col gap-3 p-5">
          <span className="col-head">{tr.invoices.identity}</span>
          <Field label={tr.invoices.supplier} value={invoice.supplier_name} />
          <Field label={tr.invoices.invoiceNo} value={invoice.invoice_no} mono />
          <Field label={tr.invoices.invoiceDate} value={formatDate(invoice.invoice_date)} />
          <Field label={tr.invoices.currency} value={invoice.currency} />
          <div className="my-1 h-px bg-divider" />
          <Field
            label={tr.invoices.declaredTotal}
            value={declared === null ? "—" : formatMoney(declared)}
          />
          <Field label={tr.invoices.linesTotal} value={formatMoney(linesTotal)} />
          <Field
            label={tr.invoices.lineCount}
            value={`${invoice.lines.length}${unmatched ? ` · ${unmatched} ${tr.invoices.unmatchedShort}` : ""}`}
          />
        </div>

        <div className="flex flex-col gap-2">
          <span className="col-head">
            {tr.invoices.parsedLines} · {invoice.lines.length}
          </span>

          {invoice.lines.map((line) => (
            <LineCard
              key={line.id}
              line={line}
              products={products}
              disabled={pending || confirmed}
              accent={accent}
              onMatch={(productId) => match(line.id, productId)}
            />
          ))}

          <p className="text-helper text-ink-muted">{tr.invoices.confirmNote}</p>
        </div>
      </div>

      {/* Doğrulama barı üç durumlu: toplam tutmuyor (kırmızı) → eşleşmemiş satır var
          (amber) → hazır (yeşil). Sunucu da aynı iki şartı arar; buton, kaybedeceği bir
          isteği göndermek yerine kapalı durur. */}
      <div
        className={`sticky bottom-0 flex flex-wrap items-center gap-3 rounded-card border p-4 ${
          !totalsOk
            ? "border-negative-border bg-negative-tint"
            : unmatched > 0
              ? "border-estimated-border bg-estimated-tint"
              : "border-hairline bg-surface"
        }`}
      >
        {ready ? (
          <Check className="h-4 w-4 shrink-0 text-positive" aria-hidden />
        ) : (
          <TriangleAlert
            className={`h-4 w-4 shrink-0 ${totalsOk ? "text-estimated" : "text-negative"}`}
            aria-hidden
          />
        )}
        <span
          className={`text-cell ${
            !totalsOk ? "text-negative" : unmatched > 0 ? "text-estimated-text" : ""
          }`}
        >
          {!totalsOk
            ? tr.invoices.totalsMismatch
                .replace("{lines}", formatMoney(linesTotal))
                .replace("{declared}", formatMoney(declared ?? 0))
                .replace("{difference}", formatMoney(Math.abs(difference)))
            : unmatched > 0
              ? tr.invoices.unmatchedBlocks.replace("{count}", String(unmatched))
              : tr.invoices.totalsMatch.replace("{total}", formatMoney(linesTotal))}
        </span>

        <div className="flex-1" />

        {confirmed ? (
          <span className="badge border-positive-border bg-positive-tint text-positive-text">
            {tr.invoices.confirmed}
          </span>
        ) : (
          <button
            type="button"
            onClick={confirm}
            disabled={pending || !ready}
            className="h-[34px] shrink-0 rounded-control px-3.5 text-cell font-medium text-white disabled:cursor-not-allowed disabled:bg-hairline disabled:text-ink-muted"
            style={ready && !pending ? { backgroundColor: accent } : undefined}
          >
            {tr.invoices.confirm}
          </button>
        )}
      </div>
    </div>
  );
}

function LineCard({
  line,
  products,
  disabled,
  accent,
  onMatch,
}: {
  line: InvoiceLine;
  products: PriceRow[];
  disabled: boolean;
  accent: string;
  onMatch: (productId: string) => void;
}) {
  const matched = line.product_id !== null;
  const suggestion = line.suggestions[0];
  const amount = toNumber(line.unit_price_try) * toNumber(line.qty);

  return (
    <div
      className={`rounded-card border p-4 ${
        matched ? "border-hairline bg-surface" : suggestion ? "border-estimated-border bg-surface" : "border-hairline bg-canvas"
      }`}
    >
      <div className="flex items-start gap-3">
        {matched ? (
          <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-positive" aria-hidden />
        ) : suggestion ? (
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-estimated" aria-hidden />
        ) : (
          <CircleDashed className="mt-0.5 h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
        )}

        <div className="min-w-0 flex-1">
          <div className="truncate font-medium uppercase">{line.raw_text}</div>
          <div className="mt-0.5 text-helper text-ink-body">
            {formatQuantity(line.qty)} {tr.invoices.pieces} × {formatMoney(line.unit_price_try)} ={" "}
            {formatMoney(amount)} · {tr.table.vat} {formatPercent(line.vat_rate)}
          </div>
        </div>

        {matched ? (
          <span className="badge shrink-0 border-positive-border bg-positive-tint text-positive-text">
            <span className="font-mono">{line.sku}</span> · {tr.invoices.automatic}
          </span>
        ) : null}
      </div>

      {matched ? null : (
        <div className="mt-3 flex flex-wrap items-center gap-2 pl-7">
          {suggestion ? (
            <>
              <span className="badge border-estimated-border bg-estimated-tint text-estimated-text">
                {tr.invoices.suggestion} <span className="font-mono">{suggestion.sku}</span>{" "}
                {formatConfidence(suggestion.confidence)}
              </span>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onMatch(suggestion.product_id)}
                className="h-7 rounded-control px-2.5 text-helper font-medium text-white disabled:opacity-40"
                style={{ backgroundColor: accent }}
              >
                {tr.invoices.approve}
              </button>
            </>
          ) : null}

          <select
            defaultValue=""
            disabled={disabled}
            onChange={(event) => {
              if (event.target.value) onMatch(event.target.value);
            }}
            className="h-7 rounded-control border border-hairline bg-surface px-2 text-helper"
          >
            <option value="">{suggestion ? tr.invoices.change : tr.invoices.chooseSku}</option>
            {products.map((product) => (
              <option key={product.product_id} value={product.product_id}>
                {product.sku} — {product.name}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-cell">
      <span className="text-ink-body">{label}</span>
      <span className={`text-right font-medium ${mono ? "font-mono text-micro" : ""}`}>
        {value}
      </span>
    </div>
  );
}

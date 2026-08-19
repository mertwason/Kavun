"use client";

/**
 * Fatura onay ekranı (tasarım brief'i, kalıp 6).
 *
 * Ayrıştırılmış satırlar + SKU eşleştirme durumu: otomatik eşleşen yeşil check,
 * öneri amber (onay ister), eşleşmeyen gri (manuel seçim). Alt barda toplam kontrolü.
 * Onaydan önce stoka hiçbir şey yazılmaz.
 */

import { useState, useTransition } from "react";

import { confirmAction, matchLineAction } from "@/app/[brand]/invoices/actions";
import type { InvoiceDetail, PriceRow } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatMoney, formatPercent, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

const STATUS_LABELS: Record<string, string> = tr.invoices.matchStatus;

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

  const confirmed = invoice.status === "confirmed";
  const unmatched = invoice.lines.filter((line) => line.product_id === null);
  const linesTotal = invoice.lines.reduce(
    (sum, line) => sum + toNumber(line.unit_price_try) * toNumber(line.qty),
    0,
  );
  const totalsOk =
    invoice.total !== null && Math.abs(linesTotal - toNumber(invoice.total)) <= 0.1;

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
      {message ? <p className="text-sm text-negative">{message}</p> : null}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-hairline text-xs font-medium text-ink-faint">
              <th className="px-3 py-2 text-left">{tr.invoices.rawText}</th>
              <th className="px-3 py-2 text-right">{tr.table.qty}</th>
              <th className="px-3 py-2 text-right">{tr.invoices.unitPrice}</th>
              <th className="px-3 py-2 text-right">{tr.table.vat}</th>
              <th className="px-3 py-2 text-left">{tr.invoices.matchedSku}</th>
            </tr>
          </thead>
          <tbody>
            {invoice.lines.map((line) => {
              const isMatched = line.product_id !== null;
              const hasSuggestion = !isMatched && line.suggestions.length > 0;
              return (
                <tr
                  key={line.id}
                  className={`border-b border-hairline ${
                    isMatched ? "" : hasSuggestion ? "bg-estimated/[0.06]" : "bg-canvas"
                  }`}
                >
                  <td className="px-3 py-2">{line.raw_text}</td>
                  <td className="px-3 py-2 text-right tabular">{String(line.qty)}</td>
                  <td className="px-3 py-2 text-right tabular">
                    {formatMoney(line.unit_price_try)}
                  </td>
                  <td className="px-3 py-2 text-right tabular">
                    {formatPercent(line.vat_rate)}
                  </td>
                  <td className="px-3 py-2">
                    {isMatched ? (
                      <span className="flex items-center gap-2">
                        <span aria-hidden className="text-positive">
                          ✓
                        </span>
                        <span className="font-mono text-xs">{line.sku}</span>
                        <span className="text-xs text-ink-faint">
                          {STATUS_LABELS[line.match_status] ?? line.match_status}
                        </span>
                      </span>
                    ) : confirmed ? (
                      <span className="text-xs text-ink-faint">—</span>
                    ) : (
                      <span className="flex flex-wrap items-center gap-2">
                        <select
                          defaultValue={
                            line.suggestions.length > 0 ? line.suggestions[0].product_id : ""
                          }
                          disabled={pending}
                          onChange={(event) => {
                            if (event.target.value) match(line.id, event.target.value);
                          }}
                          className="rounded-card border border-hairline bg-surface px-2 py-1 text-xs"
                        >
                          <option value="">{tr.invoices.chooseSku}</option>
                          {line.suggestions.map((suggestion) => (
                            <option key={suggestion.product_id} value={suggestion.product_id}>
                              ⚑ {suggestion.sku} — {suggestion.name} (
                              {formatPercent(toNumber(suggestion.confidence) * 100)})
                            </option>
                          ))}
                          {products.map((product) => (
                            <option key={product.product_id} value={product.product_id}>
                              {product.sku} — {product.name}
                            </option>
                          ))}
                        </select>
                        {hasSuggestion ? (
                          <span className="text-xs text-estimated">
                            {tr.invoices.suggestionNeedsApproval}
                          </span>
                        ) : null}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-4 border-t border-hairline pt-3 text-sm">
        <span className={totalsOk ? "text-positive" : "text-negative"}>
          {totalsOk ? "✓ " : "⚠ "}
          {tr.invoices.totalCheck}: {formatMoney(linesTotal)}
          {invoice.total !== null ? ` / ${formatMoney(invoice.total)}` : ""}
        </span>
        <span className="text-ink-faint">
          {tr.invoices.unmatchedCount}: <span className="tabular">{unmatched.length}</span>
        </span>
        {confirmed ? (
          <span className="ml-auto text-positive">{tr.invoices.confirmed}</span>
        ) : (
          <button
            type="button"
            onClick={confirm}
            disabled={pending || unmatched.length > 0}
            className="ml-auto rounded-card border border-ink bg-ink px-3 py-1.5 text-sm text-surface disabled:opacity-40"
          >
            {pending ? tr.pricelist.applying : tr.invoices.confirm}
          </button>
        )}
      </div>
      {!confirmed ? (
        <p className="text-xs text-ink-faint">{tr.invoices.confirmNote}</p>
      ) : (
        <p className="text-xs text-ink-faint">{tr.invoices.immutableNote}</p>
      )}
    </div>
  );
}

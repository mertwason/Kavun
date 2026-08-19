/** Fatura onay ekranı — handoff `Fatura Yukleme.dc.html` (spec §12C.3). */

import { InvoiceReview } from "@/components/invoice-review";
import { Card, ErrorState, TextLink } from "@/components/ui";
import { fetchInvoice, fetchPriceRows } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatDate } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const STATUS_STYLE: Record<string, string> = {
  parsed: "border-hairline bg-canvas text-ink-secondary",
  review: "border-estimated-border bg-estimated-tint text-estimated-text",
  confirmed: "border-positive-border bg-positive-tint text-positive-text",
};

const STATUS_LABELS: Record<string, string> = tr.invoices.status;

export default async function InvoiceDetailPage({
  params,
}: {
  params: { brand: BrandSlug; invoiceId: string };
}) {
  const [invoice, rows] = await Promise.all([
    fetchInvoice(params.brand, params.invoiceId),
    fetchPriceRows(params.brand),
  ]);

  if (!invoice.ok) {
    return (
      <>
        <TextLink href={`/${params.brand}/invoices`}>← {tr.invoices.backToList}</TextLink>
        <Card>
          <ErrorState status={invoice.status} />
        </Card>
      </>
    );
  }

  const products = rows.ok
    ? rows.data.filter(
        (row, index, all) => all.findIndex((item) => item.product_id === row.product_id) === index,
      )
    : [];

  return (
    <>
      <TextLink href={`/${params.brand}/invoices`}>← {tr.invoices.backToList}</TextLink>

      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-title font-medium">{invoice.data.invoice_no}</h1>
        <span className={`badge ${STATUS_STYLE[invoice.data.status] ?? ""}`}>
          {STATUS_LABELS[invoice.data.status] ?? invoice.data.status}
        </span>
        <span className="text-helper text-ink-body">
          {invoice.data.supplier_name} · {formatDate(invoice.data.invoice_date)}
        </span>
      </div>

      <InvoiceReview brand={params.brand} invoice={invoice.data} products={products} />
    </>
  );
}

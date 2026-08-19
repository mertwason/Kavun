/** Fatura onay ekranı — satır eşleştirme + toplam kontrolü (tasarım brief'i, kalıp 6). */

import { InvoiceReview } from "@/components/invoice-review";
import { Card, ErrorState, SectionHeader, TextLink } from "@/components/ui";
import { fetchInvoice, fetchPriceRows } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatDate } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

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

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-xs uppercase tracking-wide text-ink-faint">
            {tr.invoices.invoiceNo}
          </span>
          <h1 className="font-mono text-lg font-medium">{invoice.data.invoice_no}</h1>
          <p className="text-xs text-ink-faint">
            {formatDate(invoice.data.invoice_date)} · {invoice.data.supplier_name} ·{" "}
            {STATUS_LABELS[invoice.data.status] ?? invoice.data.status}
          </p>
        </div>
      </div>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.invoices.reviewTitle} subtitle={tr.invoices.reviewSubtitle} />
        <InvoiceReview brand={params.brand} invoice={invoice.data} products={products} />
      </Card>
    </>
  );
}

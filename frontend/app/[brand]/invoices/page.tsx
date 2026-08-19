/**
 * Fatura listesi + PDF yükleme — handoff `Fatura Yukleme.dc.html` (spec §12C.3, §12C.5).
 *
 * Hiç fatura yoksa ekranda **yalnızca** bırakma alanı kalır (handoff boş durumu); fatura
 * varsa yükleyici üstte, liste altında durur.
 */

import Link from "next/link";

import { InvoiceUpload } from "@/components/invoice-upload";
import { Card, DataTable, ErrorState, SectionHeader, Td, Th, Tr } from "@/components/ui";
import { fetchInvoices, fetchSuppliers } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatDate, formatMoney } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const STATUS_STYLE: Record<string, string> = {
  parsed: "border-hairline bg-canvas text-ink-secondary",
  review: "border-estimated-border bg-estimated-tint text-estimated-text",
  confirmed: "border-positive-border bg-positive-tint text-positive-text",
};

const STATUS_LABELS: Record<string, string> = tr.invoices.status;

export default async function InvoicesPage({ params }: { params: { brand: BrandSlug } }) {
  const [invoices, suppliers] = await Promise.all([
    fetchInvoices(params.brand),
    fetchSuppliers(params.brand),
  ]);

  const empty = invoices.ok && invoices.data.length === 0;
  // Liste ucu tedarikçi adını taşımıyor (yalnız `supplier_id`); zaten çektiğimiz
  // tedarikçi listesinden çözüyoruz — şema değiştirmeye gerek yok.
  const supplierNames = new Map(
    suppliers.ok ? suppliers.data.map((item) => [item.id, item.name] as const) : [],
  );

  return (
    <>
      <h1 className="sr-only">{tr.nav.invoices}</h1>

      <Card className="flex flex-col gap-4 p-5">
        {empty ? null : (
          <SectionHeader title={tr.invoices.uploadTitle} subtitle={tr.invoices.uploadSubtitle} />
        )}
        <InvoiceUpload
          brand={params.brand}
          suppliers={
            suppliers.ok ? suppliers.data.map((item) => ({ id: item.id, name: item.name })) : []
          }
        />
      </Card>

      {empty ? null : (
        <Card className="overflow-hidden">
          {!invoices.ok ? (
            <ErrorState status={invoices.status} />
          ) : (
            <DataTable
              head={
                <>
                  <Th>{tr.invoices.invoiceNo}</Th>
                  <Th>{tr.invoices.supplier}</Th>
                  <Th>{tr.table.date}</Th>
                  <Th align="right">{tr.table.total}</Th>
                  <Th>{tr.table.state}</Th>
                </>
              }
            >
              {invoices.data.map((invoice) => (
                <Tr key={invoice.id}>
                  <Td>
                    <Link
                      href={`/${params.brand}/invoices/${invoice.id}`}
                      className="font-mono text-micro text-ink-secondary underline decoration-ink-ghost underline-offset-4 hover:text-ink"
                    >
                      {invoice.invoice_no}
                    </Link>
                  </Td>
                  <Td className="text-ink-secondary">
                    {supplierNames.get(invoice.supplier_id) ?? "—"}
                  </Td>
                  <Td className="text-ink-secondary">{formatDate(invoice.invoice_date)}</Td>
                  <Td align="right">
                    {invoice.total === null ? "—" : formatMoney(invoice.total)}
                  </Td>
                  <Td>
                    <span className={`badge ${STATUS_STYLE[invoice.status] ?? ""}`}>
                      {STATUS_LABELS[invoice.status] ?? invoice.status}
                    </span>
                  </Td>
                </Tr>
              ))}
            </DataTable>
          )}
        </Card>
      )}
    </>
  );
}

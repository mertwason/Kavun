/** Fatura listesi + PDF yükleme (spec §12C.3, §12C.5). */

import Link from "next/link";

import { InvoiceUpload } from "@/components/invoice-upload";
import {
  Card,
  DataTable,
  EmptyState,
  ErrorState,
  SectionHeader,
  Td,
  Th,
  Tr,
} from "@/components/ui";
import { fetchInvoices, fetchSuppliers } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatDate, formatMoney } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const STATUS_LABELS: Record<string, string> = tr.invoices.status;

export default async function InvoicesPage({ params }: { params: { brand: BrandSlug } }) {
  const [invoices, suppliers] = await Promise.all([
    fetchInvoices(params.brand),
    fetchSuppliers(params.brand),
  ]);

  return (
    <>
      <h1 className="text-lg font-medium">{tr.nav.invoices}</h1>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.invoices.uploadTitle} subtitle={tr.invoices.uploadSubtitle} />
        <InvoiceUpload
          brand={params.brand}
          suppliers={suppliers.ok ? suppliers.data.map((item) => ({ id: item.id, name: item.name })) : []}
        />
      </Card>

      <Card>
        {!invoices.ok ? (
          <ErrorState status={invoices.status} />
        ) : invoices.data.length === 0 ? (
          <EmptyState title={tr.empty.invoices} hint={tr.empty.invoicesHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.invoices.invoiceNo}</Th>
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
                    className="font-mono text-xs underline underline-offset-4 hover:text-ink"
                  >
                    {invoice.invoice_no}
                  </Link>
                </Td>
                <Td className="text-ink-muted">{formatDate(invoice.invoice_date)}</Td>
                <Td align="right">
                  {invoice.total === null ? "—" : formatMoney(invoice.total)}
                </Td>
                <Td className="text-ink-muted">
                  {STATUS_LABELS[invoice.status] ?? invoice.status}
                </Td>
              </Tr>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  );
}

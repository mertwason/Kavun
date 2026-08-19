/**
 * Kargo faturaları ekranı (spec §5.3, §6.2).
 *
 * Kâr motorunun "tahmini" kısmının kesinleştiği yer: fatura yüklenir, gönderilerle
 * eşleşir, maliyet `estimated → actual` olur ve etkilenen siparişlerin kârı revize edilir.
 */

import { CargoUpload } from "@/components/cargo-upload";
import { KpiCard } from "@/components/kpi-card";
import { Card, DataTable, EmptyState, SectionHeader, Td, Th, Tr } from "@/components/ui";
import { fetchCargoCostState, fetchCargoInvoices } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatCount, formatDateTime, formatMoney, formatPercent } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function CargoPage({ params }: { params: { brand: BrandSlug } }) {
  const [invoices, state] = await Promise.all([
    fetchCargoInvoices(params.brand),
    fetchCargoCostState(params.brand),
  ]);

  const summary = state.ok ? state.data : null;
  const finalRate = summary && summary.total > 0 ? (summary.actual / summary.total) * 100 : 0;

  return (
    <>
      <h1 className="text-title font-medium">{tr.cargo.title}</h1>
      <p className="-mt-4 text-helper text-ink-muted">{tr.cargo.subtitle}</p>

      <div className="grid gap-4 sm:grid-cols-4">
        <KpiCard
          label={tr.cargo.shipments}
          value={formatCount(summary?.total ?? 0)}
          hint={tr.cargo.stateTitle}
        />
        <KpiCard
          label={tr.cargo.actualCount}
          value={formatCount(summary?.actual ?? 0)}
          hint={formatPercent(finalRate)}
        />
        <KpiCard
          label={tr.cargo.estimatedCount}
          value={formatCount(summary?.estimated ?? 0)}
          tone={summary && summary.estimated > 0 ? "negative" : "neutral"}
        />
        <KpiCard
          label={tr.cargo.actualAmount}
          value={formatMoney(summary?.actual_amount ?? 0)}
          hint={`${tr.cargo.estimatedAmount}: ${formatMoney(summary?.estimated_amount ?? 0)}`}
        />
      </div>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.cargo.uploadTitle} subtitle={tr.cargo.uploadSubtitle} />
        <CargoUpload brand={params.brand} />
      </Card>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.cargo.listTitle} />
        </div>
        {!invoices.ok || invoices.data.length === 0 ? (
          <EmptyState title={tr.empty.cargo} hint={tr.empty.cargoHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.cargo.invoiceNo}</Th>
                <Th>{tr.cargo.period}</Th>
                <Th align="right">{tr.cargo.total}</Th>
                <Th>{tr.table.date}</Th>
              </>
            }
          >
            {invoices.data.map((invoice) => (
              <Tr key={invoice.id}>
                <Td className="font-mono text-helper text-ink-muted">{invoice.invoice_no}</Td>
                <Td>{invoice.period}</Td>
                <Td align="right">{formatMoney(invoice.total)}</Td>
                <Td className="text-ink-muted">{formatDateTime(invoice.created_at)}</Td>
              </Tr>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  );
}

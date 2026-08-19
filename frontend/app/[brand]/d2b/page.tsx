/**
 * D2B / kurumsal satış ekranı (spec §12C.9).
 *
 * Satışlar normal sipariş olarak yazılır: stok düşer, komisyon 0, marka P&L'ine girer.
 * Modül bayrağı kapalı markada API 404 döner; ekran bunu "kapalı modül" olarak gösterir.
 */

import { D2bUpload } from "@/components/d2b-upload";
import { Card, DataTable, EmptyState, SectionHeader, Td, Th, Tr } from "@/components/ui";
import { fetchTierMargins } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatCount, formatMoney, formatPercent } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function D2bPage({ params }: { params: { brand: BrandSlug } }) {
  const tiers = await fetchTierMargins(params.brand);

  if (!tiers.ok && tiers.status === 404) {
    return (
      <>
        <h1 className="text-lg font-medium">{tr.d2b.title}</h1>
        <Card>
          <EmptyState title={tr.d2b.disabled} hint={tr.d2b.disabledHint} />
        </Card>
      </>
    );
  }

  return (
    <>
      <h1 className="text-lg font-medium">{tr.d2b.title}</h1>
      <p className="-mt-4 text-xs text-ink-faint">{tr.d2b.subtitle}</p>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.d2b.uploadTitle} subtitle={tr.d2b.uploadSubtitle} />
        <D2bUpload brand={params.brand} />
      </Card>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.d2b.tiersTitle} subtitle={tr.d2b.tiersSubtitle} />
        </div>
        {!tiers.ok || tiers.data.length === 0 ? (
          <EmptyState title={tr.empty.d2b} hint={tr.empty.d2bHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.d2b.tier}</Th>
                <Th align="right">{tr.d2b.customerCount}</Th>
                <Th align="right">{tr.d2b.orders}</Th>
                <Th align="right">{tr.d2b.qty}</Th>
                <Th align="right">{tr.d2b.revenue}</Th>
                <Th align="right">{tr.d2b.avgDiscount}</Th>
              </>
            }
          >
            {tiers.data.map((row) => (
              <Tr key={row.tier}>
                <Td>{row.tier}</Td>
                <Td align="right">{formatCount(row.customers)}</Td>
                <Td align="right">{formatCount(row.orders)}</Td>
                <Td align="right">{formatCount(row.qty)}</Td>
                <Td align="right">{formatMoney(row.revenue)}</Td>
                <Td align="right">{formatPercent(row.avg_discount_pct)}</Td>
              </Tr>
            ))}
          </DataTable>
        )}
      </Card>
    </>
  );
}

/** Ürün Çalışma Alanı — fiyat listesi + Excel aktar/yükle (spec §12A.5). */

import { PriceImport } from "@/components/price-import";
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
import { fetchPriceRows, fetchViolations } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatMoney, formatPercent, signClass, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function ProductsPage({ params }: { params: { brand: BrandSlug } }) {
  const [result, violations] = await Promise.all([
    fetchPriceRows(params.brand),
    fetchViolations(params.brand),
  ]);

  // Modül kapalıysa (404) disiplin kartı hiç gösterilmez — spec §3A.4.
  const disciplineRows = violations.ok ? violations.data : [];

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-medium">{tr.nav.products}</h1>
        <a
          href={`/${params.brand}/products/download`}
          className="rounded-card border border-hairline px-3 py-1.5 text-sm hover:bg-canvas"
        >
          {tr.pricelist.export}
        </a>
      </div>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.pricelist.importTitle} subtitle={tr.pricelist.importSubtitle} />
        <PriceImport brand={params.brand} />
      </Card>

      <Card>
        {!result.ok ? (
          <ErrorState status={result.status} />
        ) : result.data.length === 0 ? (
          <EmptyState title={tr.empty.products} hint={tr.empty.productsHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.table.sku}</Th>
                <Th>{tr.table.product}</Th>
                <Th>{tr.pricelist.channel}</Th>
                <Th align="right">{tr.table.vat}</Th>
                <Th align="right">{tr.pricelist.desi}</Th>
                <Th align="right">{tr.table.cost}</Th>
                <Th align="right">{tr.pricelist.price}</Th>
                <Th align="right">{tr.pricelist.commission}</Th>
                <Th align="right">{tr.table.profit}</Th>
                <Th align="right">{tr.table.margin}</Th>
              </>
            }
          >
            {result.data.map((row) => (
              <Tr
                key={`${row.product_id}-${row.channel}`}
                negative={row.price !== null && toNumber(row.profit) < 0}
              >
                <Td className="font-mono text-xs text-ink-muted">{row.sku}</Td>
                <Td>{row.name}</Td>
                <Td className="text-ink-muted">{row.channel}</Td>
                <Td align="right">{formatPercent(row.vat_rate)}</Td>
                <Td align="right">{row.desi === null ? "—" : String(row.desi)}</Td>
                <Td align="right">
                  {row.unit_cost === null ? "—" : formatMoney(row.unit_cost)}
                </Td>
                <Td align="right">{row.price === null ? "—" : formatMoney(row.price)}</Td>
                <Td align="right">
                  {row.commission_rate === null
                    ? "—"
                    : formatPercent(toNumber(row.commission_rate) * 100)}
                </Td>
                <Td align="right" className={row.price === null ? "" : signClass(row.profit)}>
                  {row.price === null ? "—" : formatMoney(row.profit)}
                </Td>
                <Td align="right" className={row.price === null ? "" : signClass(row.margin_pct)}>
                  {row.price === null ? "—" : formatPercent(row.margin_pct)}
                </Td>
              </Tr>
            ))}
          </DataTable>
        )}
      </Card>

      {violations.ok ? (
        <Card className="flex flex-col">
          <div className="p-5 pb-2">
            <SectionHeader title={tr.discipline.title} subtitle={tr.discipline.subtitle} />
          </div>
          {disciplineRows.length === 0 ? (
            <EmptyState title={tr.empty.discipline} hint={tr.empty.disciplineHint} />
          ) : (
            <DataTable
              head={
                <>
                  <Th>{tr.table.sku}</Th>
                  <Th>{tr.table.product}</Th>
                  <Th>{tr.discipline.channel}</Th>
                  <Th align="right">{tr.discipline.price}</Th>
                  <Th align="right">{tr.discipline.msrp}</Th>
                  <Th align="right">{tr.discipline.gap}</Th>
                  <Th align="right">{tr.discipline.margin}</Th>
                  <Th align="right">{tr.discipline.floor}</Th>
                  <Th>{tr.discipline.kind}</Th>
                </>
              }
            >
              {disciplineRows.map((row) => (
                <Tr key={`${row.product_id}-${row.channel}`}>
                  <Td className="font-mono text-xs text-ink-muted">{row.sku}</Td>
                  <Td>{row.name}</Td>
                  <Td className="text-ink-muted">{row.channel}</Td>
                  <Td align="right">{formatMoney(row.price)}</Td>
                  <Td align="right">{row.msrp === null ? "—" : formatMoney(row.msrp)}</Td>
                  <Td align="right" className="text-negative">
                    {row.msrp_gap_pct === null ? "—" : formatPercent(row.msrp_gap_pct)}
                  </Td>
                  <Td align="right" className={signClass(row.margin_pct)}>
                    {formatPercent(row.margin_pct)}
                  </Td>
                  <Td align="right" className="text-ink-muted">
                    {row.floor_pct === null ? "—" : formatPercent(row.floor_pct)}
                  </Td>
                  <Td className="text-xs text-ink-muted">
                    {row.kinds
                      .map((kind) =>
                        kind === "msrp" ? tr.discipline.kindMsrp : tr.discipline.kindFloor,
                      )
                      .join(" · ")}
                  </Td>
                </Tr>
              ))}
            </DataTable>
          )}
        </Card>
      ) : null}
    </>
  );
}

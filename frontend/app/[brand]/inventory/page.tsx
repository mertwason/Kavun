/**
 * Stok & maliyet ekranı (tasarım brief'i ekran 8, spec §12C.1-4).
 *
 * Üstte eldeki stok ve ağırlıklı ortalama maliyet, altta append-only hareket defteri.
 * Ortalama maliyeti yalnızca giriş hareketleri değiştirir; çıkış yalnızca adet düşürür.
 */

import Link from "next/link";

import {
  AdjustmentForm,
  DamageForm,
  OpeningStockForm,
  type ProductOption,
} from "@/components/stock-forms";
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
import { fetchDamageRows, fetchLedger, fetchStock } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import {
  formatCount,
  formatDateTime,
  formatMoney,
  formatMoneyWhole,
  formatPercent,
  toNumber,
} from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const MOVEMENT_LABELS: Record<string, string> = tr.inventory.movement;

export default async function InventoryPage({
  params,
  searchParams,
}: {
  params: { brand: BrandSlug };
  searchParams: { product?: string };
}) {
  // Seçili ürün URL'de taşınır: zaman çizelgesi paylaşılabilir ve geri tuşu çalışır.
  const selected = searchParams.product;
  const [stock, ledger, damage] = await Promise.all([
    fetchStock(params.brand),
    fetchLedger(params.brand, selected),
    fetchDamageRows(params.brand),
  ]);

  const rows = stock.ok ? stock.data : [];
  const totalValue = rows.reduce((sum, row) => sum + toNumber(row.stock_value), 0);
  const tracked = rows.filter((row) => toNumber(row.on_hand) > 0).length;
  const negative = rows.filter((row) => toNumber(row.on_hand) < 0).length;
  const products: ProductOption[] = rows.map((row) => ({
    product_id: row.product_id,
    sku: row.sku,
    name: row.name,
  }));
  const bySku = new Map(rows.map((row) => [row.product_id, row]));
  const selectedRow = selected ? bySku.get(selected) : undefined;

  return (
    <>
      <h1 className="sr-only">{tr.inventory.title}</h1>

      {/* Üst şerit: tek cümlede stok gerçeği (handoff exec strip). */}
      <Card className="flex flex-wrap items-center gap-x-8 gap-y-4 rounded-exec p-5">
        <div className="flex flex-col gap-1">
          <span className="col-head">{tr.inventory.totalValue}</span>
          <span className="text-kpi">{formatMoneyWhole(totalValue)}</span>
          <span className="text-helper text-ink-body">
            {tr.inventory.skuCount.replace("{count}", formatCount(tracked))} ·{" "}
            {tr.inventory.method}
          </span>
        </div>

        {negative > 0 ? (
          <div className="flex flex-col gap-1">
            <span className="col-head">{tr.inventory.negativeStock}</span>
            <span className="text-kpiSm text-negative">{formatCount(negative)}</span>
            <span className="text-helper text-ink-muted">{tr.inventory.negativeHint}</span>
          </div>
        ) : null}
      </Card>

      <Card className="flex flex-col overflow-hidden">
        {!stock.ok ? (
          <ErrorState status={stock.status} />
        ) : rows.length === 0 ? (
          <EmptyState title={tr.empty.stock} hint={tr.empty.stockHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.table.sku}</Th>
                <Th>{tr.table.product}</Th>
                <Th>{tr.table.category}</Th>
                <Th align="right">{tr.inventory.onHand}</Th>
                <Th align="right">{tr.inventory.avgCost}</Th>
                <Th align="right">{tr.inventory.stockValue}</Th>
                <Th>{tr.inventory.lastMovement}</Th>
              </>
            }
          >
            {rows.map((row) => (
              <Tr key={row.product_id} negative={toNumber(row.on_hand) < 0}>
                <Td className="font-mono text-micro">
                  <Link
                    href={`/${params.brand}/inventory?product=${row.product_id}`}
                    className={`underline decoration-ink-ghost underline-offset-4 hover:text-ink ${
                      selected === row.product_id ? "text-ink" : "text-ink-secondary"
                    }`}
                  >
                    {row.sku}
                  </Link>
                </Td>
                <Td>{row.name}</Td>
                <Td className="text-ink-secondary">{row.category ?? "—"}</Td>
                <Td align="right">{formatCount(toNumber(row.on_hand))}</Td>
                <Td align="right">{formatMoney(row.avg_cost)}</Td>
                <Td align="right">{formatMoney(row.stock_value)}</Td>
                <Td className="text-ink-secondary">
                  {row.last_movement_at ? formatDateTime(row.last_movement_at) : "—"}
                </Td>
              </Tr>
            ))}
          </DataTable>
        )}
        {rows.length > 0 ? (
          <div className="flex flex-wrap items-center gap-3 border-t border-hairline bg-canvas px-5 py-2.5 text-helper text-ink-body">
            <span>
              {tr.inventory.showingSkus
                .replace("{shown}", formatCount(rows.length))
                .replace("{total}", formatCount(rows.length))}
            </span>
            <span className="text-ink-ghost">·</span>
            <span>{tr.inventory.rowHint}</span>
          </div>
        ) : null}
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="flex flex-col gap-4 p-5">
          <SectionHeader
            title={tr.inventory.openingTitle}
            subtitle={tr.inventory.openingSubtitle}
          />
          <OpeningStockForm brand={params.brand} products={products} />
        </Card>

        <Card className="flex flex-col gap-4 p-5">
          <SectionHeader title={tr.inventory.adjustTitle} subtitle={tr.inventory.adjustSubtitle} />
          <AdjustmentForm brand={params.brand} products={products} />
        </Card>
      </div>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.damage.title} subtitle={tr.damage.subtitle} />
        </div>
        {!damage.ok || damage.data.length === 0 ? (
          <EmptyState title={tr.empty.damage} hint={tr.empty.damageHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.table.sku}</Th>
                <Th>{tr.table.product}</Th>
                <Th align="right">{tr.damage.qty}</Th>
                <Th align="right">{tr.damage.cost}</Th>
                <Th align="right">{tr.damage.soldQty}</Th>
                <Th align="right">{tr.damage.rate}</Th>
              </>
            }
          >
            {damage.data.map((row) => (
              <Tr key={row.product_id}>
                <Td className="font-mono text-helper text-ink-muted">{row.sku}</Td>
                <Td>{row.name}</Td>
                <Td align="right">{formatCount(toNumber(row.qty))}</Td>
                <Td align="right" className="text-negative">
                  {formatMoney(row.cost)}
                </Td>
                <Td align="right">{formatCount(toNumber(row.sold_qty))}</Td>
                <Td align="right">{formatPercent(row.damage_rate_pct)}</Td>
              </Tr>
            ))}
          </DataTable>
        )}
        <div className="border-t border-hairline p-5">
          <DamageForm brand={params.brand} products={products} />
        </div>
      </Card>

      <Card className="flex flex-col">
        <div className="flex flex-wrap items-end justify-between gap-3 p-5 pb-2">
          <SectionHeader
            title={
              selectedRow
                ? `${tr.inventory.timelineTitle} · ${selectedRow.sku}`
                : tr.inventory.ledgerTitle
            }
            subtitle={
              selectedRow
                ? `${selectedRow.name} · ${formatCount(toNumber(selectedRow.on_hand))} ${tr.invoices.pieces} · ${tr.inventory.avgCost.toLocaleLowerCase("tr-TR")} ${formatMoney(selectedRow.avg_cost)}`
                : tr.inventory.ledgerSubtitle
            }
          />
          {selectedRow ? (
            <Link
              href={`/${params.brand}/inventory`}
              className="text-helper text-ink-secondary underline decoration-ink-ghost underline-offset-4 hover:text-ink"
            >
              {tr.inventory.allProducts}
            </Link>
          ) : null}
        </div>
        {!ledger.ok ? (
          <ErrorState status={ledger.status} />
        ) : ledger.data.length === 0 ? (
          <EmptyState title={tr.empty.ledger} hint={tr.empty.ledgerHint} />
        ) : (
          <div className="max-h-[32rem] overflow-auto">
            <DataTable
              head={
                <>
                  <Th>{tr.table.date}</Th>
                  <Th>{tr.table.sku}</Th>
                  <Th>{tr.table.status}</Th>
                  <Th align="right">{tr.table.qty}</Th>
                  <Th align="right">{tr.inventory.unitCost}</Th>
                  <Th align="right">{tr.inventory.afterMovement}</Th>
                  <Th>{tr.inventory.reference}</Th>
                </>
              }
            >
              {ledger.data.map((entry) => {
                const product = bySku.get(entry.product_id);
                const delta = toNumber(entry.qty_delta);
                return (
                  <Tr key={entry.id}>
                    <Td className="text-ink-muted">{formatDateTime(entry.moved_at)}</Td>
                    <Td className="font-mono text-helper text-ink-muted">{product?.sku ?? "—"}</Td>
                    <Td>{MOVEMENT_LABELS[entry.movement] ?? entry.movement}</Td>
                    <Td align="right" className={delta < 0 ? "text-negative" : ""}>
                      {delta > 0 ? "+" : ""}
                      {formatCount(delta)}
                    </Td>
                    <Td align="right">
                      {entry.unit_cost_at_movement === null
                        ? "—"
                        : formatMoney(entry.unit_cost_at_movement)}
                    </Td>
                    <Td align="right">
                      {formatCount(toNumber(entry.on_hand_after))} ·{" "}
                      {formatMoney(entry.avg_cost_after)}
                    </Td>
                    <Td className="text-helper text-ink-muted">
                      {entry.reason ?? entry.ref_type ?? "—"}
                    </Td>
                  </Tr>
                );
              })}
            </DataTable>
          </div>
        )}
      </Card>
    </>
  );
}

/**
 * Stok & maliyet ekranı (tasarım brief'i ekran 8, spec §12C.1-4).
 *
 * Üstte eldeki stok ve ağırlıklı ortalama maliyet, altta append-only hareket defteri.
 * Ortalama maliyeti yalnızca giriş hareketleri değiştirir; çıkış yalnızca adet düşürür.
 */

import { KpiCard } from "@/components/kpi-card";
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
import { formatCount, formatDateTime, formatMoney, formatPercent, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const MOVEMENT_LABELS: Record<string, string> = tr.inventory.movement;

export default async function InventoryPage({ params }: { params: { brand: BrandSlug } }) {
  const [stock, ledger, damage] = await Promise.all([
    fetchStock(params.brand),
    fetchLedger(params.brand),
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

  return (
    <>
      <h1 className="text-lg font-medium">{tr.inventory.title}</h1>
      <p className="-mt-4 text-xs text-ink-faint">{tr.inventory.subtitle}</p>

      <div className="grid gap-4 sm:grid-cols-3">
        <KpiCard label={tr.inventory.totalValue} value={formatMoney(totalValue)} />
        <KpiCard label={tr.inventory.trackedSkus} value={formatCount(tracked)} />
        <KpiCard
          label={tr.inventory.negativeStock}
          value={formatCount(negative)}
          tone={negative > 0 ? "negative" : "neutral"}
          hint={negative > 0 ? tr.inventory.negativeHint : undefined}
        />
      </div>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.inventory.title} />
        </div>
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
                <Td className="font-mono text-xs text-ink-muted">{row.sku}</Td>
                <Td>{row.name}</Td>
                <Td className="text-ink-muted">{row.category ?? "—"}</Td>
                <Td align="right">{formatCount(toNumber(row.on_hand))}</Td>
                <Td align="right">{formatMoney(row.avg_cost)}</Td>
                <Td align="right">{formatMoney(row.stock_value)}</Td>
                <Td className="text-ink-muted">
                  {row.last_movement_at ? formatDateTime(row.last_movement_at) : "—"}
                </Td>
              </Tr>
            ))}
          </DataTable>
        )}
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
                <Td className="font-mono text-xs text-ink-muted">{row.sku}</Td>
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
        <div className="p-5 pb-2">
          <SectionHeader title={tr.inventory.ledgerTitle} subtitle={tr.inventory.ledgerSubtitle} />
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
                    <Td className="font-mono text-xs text-ink-muted">{product?.sku ?? "—"}</Td>
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
                    <Td className="text-xs text-ink-faint">
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

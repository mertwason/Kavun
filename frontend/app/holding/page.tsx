/**
 * Holding görünümü — handoff `Holding.dc.html` (spec §3A.3).
 *
 * Salt okunur: burada hiçbir işlem yapılamaz, hiçbir form yoktur. Yetkisiz kullanıcıda
 * API 403 döner ve ekran bunu açık bir mesajla gösterir.
 *
 * Ana blok **transpoze P&L**: satırlar kalem (ciro, satış maliyeti, pazaryeri kesintileri,
 * net kâr, marj), kolonlar marka + toplam. Markaları yan yana okumanın tek doğru yolu bu.
 *
 * **Tasarımdan sapma:** handoff'ta bir de "Aylık Net Kâr Trendi" grafiği var. Kavun aylık
 * kâr serisini saklamıyor (kâr satır bazında yazılıyor, dönem sorgusuyla toplanıyor), altı
 * aylık seriyi çıkarmak için ayrı bir toplama katmanı gerekiyor. Uydurma seri çizmek yerine
 * o blok bırakıldı; seri gerçekten gerektiğinde önce veri tarafı yazılmalı.
 */

import Link from "next/link";

import { Card, EmptyState } from "@/components/ui";
import { fetchConsolidated } from "@/lib/api";
import type { Consolidated } from "@/lib/api";
import { BRANDS, isBrandSlug } from "@/lib/brands";
import {
  formatAmount,
  formatCount,
  formatDate,
  formatMoney,
  formatMoneyWhole,
  formatPercent,
  signClass,
  toNumber,
} from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

type Brand = Consolidated["brands"][number];

export default async function HoldingPage() {
  const report = await fetchConsolidated();

  if (!report.ok) {
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-20">
        <h1 className="text-title font-medium">{tr.holding.title}</h1>
        <Card>
          <EmptyState title={tr.holding.denied} hint={tr.holding.deniedHint} />
        </Card>
        <Link href="/" className="text-cell text-ink-secondary underline underline-offset-4">
          {tr.holding.backHome}
        </Link>
      </main>
    );
  }

  const data = report.data;
  const brands = data.brands;

  /** P&L satırları: her biri marka değerini ve toplamı kendi biçimiyle yazar. */
  const rows: {
    label: string;
    value: (brand: Brand) => string;
    total: string;
    negative?: boolean;
    strong?: boolean;
  }[] = [
    {
      label: tr.holding.revenue,
      value: (brand) => formatMoneyWhole(brand.revenue),
      total: formatMoneyWhole(data.total_revenue),
    },
    {
      label: tr.holding.costGoods,
      value: (brand) => `−${formatMoneyWhole(brand.cost_goods)}`,
      total: `−${formatMoneyWhole(data.total_cost_goods)}`,
      negative: true,
    },
    {
      label: tr.holding.deductions,
      value: (brand) => `−${formatMoneyWhole(brand.marketplace_deductions)}`,
      total: `−${formatMoneyWhole(data.total_marketplace_deductions)}`,
      negative: true,
    },
    {
      label: tr.holding.profit,
      value: (brand) => formatMoneyWhole(brand.profit),
      total: formatMoneyWhole(data.total_profit),
      strong: true,
    },
    {
      label: tr.holding.margin,
      value: (brand) => formatPercent(brand.margin_pct),
      total: formatPercent(
        toNumber(data.total_revenue) === 0
          ? 0
          : (toNumber(data.total_profit) / toNumber(data.total_revenue)) * 100,
      ),
    },
  ];

  return (
    <main className="mx-auto flex w-full max-w-content flex-col gap-4 p-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-title font-medium">{tr.holding.title}</h1>
        <span className="badge border-hairline bg-canvas text-ink-muted">
          {tr.holding.readOnly}
        </span>
        <div className="flex-1" />
        <span className="text-helper text-ink-muted">
          {formatDate(data.since)} — {formatDate(data.until)}
        </span>
      </div>

      <Card className="flex flex-col overflow-hidden rounded-exec">
        <div className="flex flex-col gap-0.5 p-5 pb-3">
          <h2 className="text-body font-medium">{tr.holding.plTitle}</h2>
          <p className="text-helper text-ink-body">
            {tr.holding.plSubtitle
              .replace("{since}", formatDate(data.since))
              .replace("{until}", formatDate(data.until))}
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-cell">
            <thead>
              <tr>
                <th className="border-b border-hairline bg-canvas px-5 py-2.5 text-left">
                  <span className="col-head">{tr.holding.brand}</span>
                </th>
                {brands.map((brand) => (
                  <th
                    key={brand.brand}
                    className="border-b border-hairline bg-canvas px-3 py-2.5 text-right"
                  >
                    <span className="col-head">
                      {isBrandSlug(brand.brand) ? (
                        <Link href={`/${brand.brand}`} className="hover:text-ink">
                          {BRANDS[brand.brand].name}
                        </Link>
                      ) : (
                        brand.name
                      )}
                    </span>
                  </th>
                ))}
                <th className="border-b border-hairline bg-canvas px-5 py-2.5 text-right">
                  <span className="col-head">{tr.holding.total}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label} className="border-b border-hairline last:border-b-0">
                  <td className="px-5 py-2.5 text-ink-body">{row.label}</td>
                  {brands.map((brand) => (
                    <td
                      key={brand.brand}
                      className={`px-3 py-2.5 text-right ${row.negative ? "text-negative" : ""} ${
                        row.strong ? `font-semibold ${signClass(brand.profit)}` : ""
                      }`}
                    >
                      {row.value(brand)}
                    </td>
                  ))}
                  <td
                    className={`px-5 py-2.5 text-right ${row.negative ? "text-negative" : ""} ${
                      row.strong ? "font-semibold" : ""
                    }`}
                  >
                    {row.total}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="flex flex-col gap-3 p-5">
          <span className="col-head">{tr.holding.stockTitle}</span>
          <span className="text-kpi">{formatMoneyWhole(data.total_stock_value)}</span>
          <div className="flex flex-col gap-1.5">
            {brands.map((brand) => (
              <div key={brand.brand} className="flex items-baseline gap-2 text-cell">
                <span className="text-ink-body">
                  {isBrandSlug(brand.brand) ? BRANDS[brand.brand].name : brand.name} ·{" "}
                  {tr.holding.skuCount.replace("{count}", formatCount(brand.product_count))}
                </span>
                <span className="flex-1 border-b border-dashed border-hairline" />
                <span>{formatMoneyWhole(brand.stock_value)}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="flex flex-col gap-3 p-5">
          <div className="flex items-center gap-2">
            <span className="col-head">{tr.holding.fxTitle}</span>
            <span className="badge border-estimated-border bg-estimated-tint text-estimated-text">
              {tr.holding.fxRisk}
            </span>
          </div>
          {brands
            .filter((brand) => toNumber(brand.open_fx_amount) !== 0)
            .map((brand) => (
              <div key={brand.brand} className="flex flex-col gap-1">
                <span className="text-kpi">{formatAmount(brand.open_fx_amount)}</span>
                <span className="text-helper text-ink-body">
                  {isBrandSlug(brand.brand) ? BRANDS[brand.brand].name : brand.name} ·{" "}
                  {tr.holding.fxDiff} {formatMoney(brand.fx_diff)}
                </span>
                <span className="text-helper text-ink-muted">
                  {tr.holding.fxHint}:{" "}
                  <span className="text-negative">
                    −{formatMoneyWhole(brand.open_fx_amount)}
                  </span>
                </span>
              </div>
            ))}
          {brands.every((brand) => toNumber(brand.open_fx_amount) === 0) ? (
            <span className="text-cell text-ink-muted">—</span>
          ) : null}
        </Card>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Link href="/" className="text-cell text-ink-secondary underline underline-offset-4">
          {tr.holding.backHome}
        </Link>
        <span className="text-helper text-ink-muted">{tr.holding.noTrend}</span>
      </div>
    </main>
  );
}

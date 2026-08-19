"use client";

/**
 * SKU marj tablosu — handoff `SKU Marjlari.dc.html`.
 *
 * Filtreler **canlı** çalışır (arama, kanal, kategori, negatif-marj anahtarı) ve tablo
 * TanStack Table üzerinde kurulu: kolon başlığına tıklayınca istemci tarafında sıralanır.
 * "Hangi SKU beni en çok zarara sokuyor" sorusu ancak sıralanabilir bir tabloda yanıtlanır.
 *
 * Rakam kolonları **daima sağa hizalı**; negatif marj satırı `#FEF7F7` zeminli ve marjı
 * kırmızı. Kargo hücresinde kesinleşmemiş maliyet amber noktayla işaretlenir.
 */

import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";
import { ChevronDown, Download, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { type ColumnMeta, DataGrid } from "@/components/data-table";
import { EstimateDot } from "@/components/estimate-dot";
import type { SkuMargin } from "@/lib/api";
import { BRANDS, type BrandSlug } from "@/lib/brands";
import { formatCount, formatMoney, formatPercent, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

const CONTROL =
  "flex h-[34px] items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 text-cell text-ink-secondary hover:border-ink-ghost hover:bg-canvas";

const column = createColumnHelper<SkuMargin>();

/** Para/oran alanları dizide geliyor; sıralama sayısal olmalı, sözlük sırası değil. */
const numeric = (accessor: (row: SkuMargin) => string | number | null) => (row: SkuMargin) =>
  toNumber(accessor(row));

const COLUMNS: ColumnDef<SkuMargin, never>[] = [
  column.accessor("sku", {
    header: () => tr.table.sku,
    cell: (info) => <span className="font-mono text-micro text-ink-muted">{info.getValue()}</span>,
    meta: { align: "left", edge: "start" } satisfies ColumnMeta,
  }),
  column.accessor("name", {
    header: () => tr.table.product,
    cell: (info) => <span className="block max-w-[260px] truncate">{info.getValue()}</span>,
    meta: { align: "left" } satisfies ColumnMeta,
  }),
  column.accessor("channel", {
    header: () => tr.sku.channel,
    cell: (info) => <ChannelBadge channel={info.getValue()} />,
    meta: { align: "left" } satisfies ColumnMeta,
  }),
  column.accessor("qty_sold", {
    header: () => tr.table.qty,
    cell: (info) => formatCount(info.getValue()),
    meta: { align: "right" } satisfies ColumnMeta,
  }),
  column.accessor(numeric((row) => row.revenue_gross), {
    id: "revenue_gross",
    header: () => tr.table.revenue,
    cell: (info) => formatMoney(info.getValue()),
    meta: { align: "right" } satisfies ColumnMeta,
  }),
  column.accessor(numeric((row) => row.unit_cost), {
    id: "unit_cost",
    header: () => tr.sku.unitCost,
    cell: (info) => formatMoney(info.getValue()),
    meta: { align: "right" } satisfies ColumnMeta,
  }),
  column.accessor(numeric((row) => row.cost_commission), {
    id: "cost_commission",
    header: () => tr.sku.commission,
    cell: (info) => formatMoney(info.getValue()),
    meta: { align: "right" } satisfies ColumnMeta,
  }),
  column.accessor(numeric((row) => row.cost_cargo), {
    id: "cost_cargo",
    header: () => tr.sku.cargo,
    cell: (info) => (
      <span className="inline-flex items-center justify-end gap-1.5">
        {info.row.original.cargo_is_final ? null : <EstimateDot />}
        {formatMoney(info.getValue())}
      </span>
    ),
    meta: { align: "right" } satisfies ColumnMeta,
  }),
  column.accessor(numeric((row) => row.profit), {
    id: "profit",
    header: () => tr.sku.netProfit,
    cell: (info) => (
      <span className={info.getValue() < 0 ? "text-negative" : "text-positive-text"}>
        {formatMoney(info.getValue())}
      </span>
    ),
    meta: { align: "right" } satisfies ColumnMeta,
  }),
  column.accessor(numeric((row) => row.margin_pct), {
    id: "margin_pct",
    header: () => tr.table.margin,
    cell: (info) => (
      <span
        className={`font-semibold ${
          toNumber(info.row.original.profit) < 0 ? "text-negative" : ""
        }`}
      >
        {formatPercent(info.getValue())}
      </span>
    ),
    meta: { align: "right", edge: "end" } satisfies ColumnMeta,
  }),
] as ColumnDef<SkuMargin, never>[];

export function SkuTable({
  rows,
  brand,
  period,
}: {
  rows: SkuMargin[];
  brand: string;
  period: { from: string; to: string };
}) {
  const [query, setQuery] = useState("");
  const [channel, setChannel] = useState("");
  const [category, setCategory] = useState("");
  const [onlyNegative, setOnlyNegative] = useState(false);
  const accent = BRANDS[brand as BrandSlug]?.accent ?? "#B45309";

  const channels = useMemo(() => unique(rows.map((row) => row.channel)), [rows]);
  const categories = useMemo(
    () => unique(rows.map((row) => row.category ?? "").filter(Boolean)),
    [rows],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("tr-TR");
    return rows.filter((row) => {
      if (onlyNegative && toNumber(row.profit) >= 0) return false;
      if (channel && row.channel !== channel) return false;
      if (category && row.category !== category) return false;
      if (!needle) return true;
      return (
        row.sku.toLocaleLowerCase("tr-TR").includes(needle) ||
        row.name.toLocaleLowerCase("tr-TR").includes(needle)
      );
    });
  }, [rows, query, channel, category, onlyNegative]);

  const totals = filtered.reduce(
    (sum, row) => ({
      revenue: sum.revenue + toNumber(row.revenue_gross),
      profit: sum.profit + toNumber(row.profit),
    }),
    { revenue: 0, profit: 0 },
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className={`${CONTROL} w-64`}>
          <Search className="h-3.5 w-3.5 shrink-0 text-ink-muted" aria-hidden />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={tr.sku.search}
            className="w-full bg-transparent outline-none placeholder:text-ink-muted"
          />
        </label>

        <Select
          value={channel}
          onChange={setChannel}
          placeholder={tr.sku.channelAll}
          options={channels}
        />
        <Select
          value={category}
          onChange={setCategory}
          placeholder={tr.sku.categoryAll}
          options={categories}
        />

        <button
          type="button"
          onClick={() => setOnlyNegative((value) => !value)}
          aria-pressed={onlyNegative}
          className={`flex h-[34px] items-center gap-2 rounded-control border px-3 text-cell font-medium ${
            onlyNegative
              ? "border-negative-border bg-negative-tint text-negative"
              : "border-hairline bg-surface text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
          }`}
        >
          <span
            aria-hidden
            className={`relative inline-block h-[15px] w-[26px] rounded-pill transition-colors ${
              onlyNegative ? "bg-negative" : "bg-hairline"
            }`}
          >
            {/* design-allow: anahtarın topuzu handoff'ta da bu küçük gölgeyle çiziliyor;
                gölge yasağı yüzey/kart gölgeleri içindir, kontrol topuzu için değil. */}
            <span
              className="absolute top-0.5 h-[11px] w-[11px] rounded-pill bg-white shadow-[0_1px_2px_rgba(0,0,0,0.2)] transition-all"
              style={{ left: onlyNegative ? "13px" : "2px" }}
            />
          </span>
          {tr.sku.onlyNegative}
        </button>

        <div className="flex-1" />

        {/* İndirilen dosya ekrandaki listeyle aynı olsun: kategori ve negatif filtresi
            sorguya taşınır. Arama sunucuda karşılığı olmadığı için taşınmaz — bunu
            butonun ipucunda açıkça yazıyoruz. */}
        <a
          href={exportHref(brand, period, { category, onlyNegative })}
          title={query ? tr.sku.exportHint : undefined}
          className="flex h-[34px] items-center gap-1.5 rounded-control px-3 text-cell font-medium text-white"
          style={{ backgroundColor: accent }}
        >
          <Download className="h-3.5 w-3.5" aria-hidden />
          {tr.sku.export}
        </a>
      </div>

      <DataGrid
        data={filtered}
        columns={COLUMNS as unknown as ColumnDef<SkuMargin, unknown>[]}
        initialSorting={[{ id: "profit", desc: true }]}
        rowKey={(row) => `${row.product_id}-${row.channel}`}
        rowClassName={(row) => (toNumber(row.profit) < 0 ? "bg-negative-row" : "hover:bg-canvas")}
        empty={<p className="p-6 text-center text-cell text-ink-muted">{tr.sku.noResult}</p>}
        footer={
          <>
            <span>
              {tr.sku.footer
                .replace("{shown}", formatCount(filtered.length))
                .replace("{total}", formatCount(rows.length))}
            </span>
            <span className="text-ink-ghost">·</span>
            <span>
              {tr.table.revenue} {formatMoney(totals.revenue)}
            </span>
            <span className="text-ink-ghost">·</span>
            <span>
              {tr.table.profit} {formatMoney(totals.profit)}
            </span>
          </>
        }
      />
    </div>
  );
}

/** Kanal harf rozeti — gerçek logo entegrasyonu ürün ekibinin kararı (handoff, Assets). */
function ChannelBadge({ channel }: { channel: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className="inline-flex h-[18px] w-[18px] items-center justify-center rounded-[5px] bg-divider text-[10px] font-semibold text-ink-secondary"
      >
        {channel.slice(0, 1).toLocaleUpperCase("tr-TR")}
      </span>
      <span className="text-ink-secondary">{channel}</span>
    </span>
  );
}

function Select({
  value,
  onChange,
  placeholder,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  options: string[];
}) {
  if (options.length === 0) return null;
  return (
    <span className={`${CONTROL} relative`}>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="appearance-none bg-transparent pr-4 outline-none"
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 h-3 w-3 text-ink-muted" aria-hidden />
    </span>
  );
}

/** Export bağlantısı — ekrandaki sunucu-tarafı filtreleriyle. */
function exportHref(
  brand: string,
  period: { from: string; to: string },
  filters: { category: string; onlyNegative: boolean },
): string {
  const query = new URLSearchParams({ from: period.from, to: period.to });
  if (filters.category) query.set("category", filters.category);
  if (filters.onlyNegative) query.set("only_negative", "true");
  return `/${brand}/sku/download?${query}`;
}

function unique(values: string[]): string[] {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b, "tr-TR"));
}

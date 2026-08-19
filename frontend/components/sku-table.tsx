"use client";

/**
 * SKU marj tablosu — handoff `SKU Marjlari.dc.html`.
 *
 * Filtreler **canlı** çalışır (arama ve negatif-marj anahtarı), bu yüzden istemci
 * bileşeni. Kanal ve kategori seçicileri de aynı listeden türetilir — sabit liste
 * yazmak yerine veriden çıkarılır, böylece markanın gerçekten sattığı kanallar görünür.
 *
 * Rakam kolonları **daima sağa hizalı**; negatif marj satırı `#FEF7F7` zeminli ve marjı
 * kırmızı. Kargo hücresinde kesinleşmemiş maliyet amber noktayla işaretlenir.
 */

import { ChevronDown, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { EstimateDot } from "@/components/estimate-dot";
import type { SkuMargin } from "@/lib/api";
import { formatCount, formatMoney, formatPercent, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

const CONTROL =
  "flex h-[34px] items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 text-cell text-ink-secondary hover:border-ink-ghost hover:bg-canvas";

export function SkuTable({ rows }: { rows: SkuMargin[] }) {
  const [query, setQuery] = useState("");
  const [channel, setChannel] = useState("");
  const [category, setCategory] = useState("");
  const [onlyNegative, setOnlyNegative] = useState(false);

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
            <span
              className="absolute top-0.5 h-[11px] w-[11px] rounded-pill bg-white shadow-[0_1px_2px_rgba(0,0,0,0.2)] transition-all"
              style={{ left: onlyNegative ? "13px" : "2px" }}
            />
          </span>
          {tr.sku.onlyNegative}
        </button>
      </div>

      <div className="overflow-hidden rounded-card border border-hairline bg-surface">
        <div className="max-h-[560px] overflow-auto">
          <table className="w-full border-collapse text-cell">
            <thead>
              <tr>
                <Head align="left" className="pl-5">
                  {tr.table.sku}
                </Head>
                <Head align="left">{tr.table.product}</Head>
                <Head align="left">{tr.sku.channel}</Head>
                <Head>{tr.table.qty}</Head>
                <Head>{tr.table.revenue}</Head>
                <Head>{tr.sku.unitCost}</Head>
                <Head>{tr.sku.commission}</Head>
                <Head>{tr.sku.cargo}</Head>
                <Head>{tr.sku.netProfit}</Head>
                <Head className="pr-5">{tr.table.margin}</Head>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => {
                const negative = toNumber(row.profit) < 0;
                return (
                  <tr
                    key={row.product_id}
                    className={`border-b border-hairline ${
                      negative ? "bg-negative-row" : "hover:bg-canvas"
                    }`}
                  >
                    <Cell className="pl-5 font-mono text-micro text-ink-muted">{row.sku}</Cell>
                    <Cell className="max-w-[260px] truncate">{row.name}</Cell>
                    <Cell>
                      <ChannelBadge channel={row.channel} />
                    </Cell>
                    <Cell align="right">{formatCount(row.qty_sold)}</Cell>
                    <Cell align="right">{formatMoney(row.revenue_gross)}</Cell>
                    <Cell align="right">{formatMoney(row.unit_cost)}</Cell>
                    <Cell align="right">{formatMoney(row.cost_commission)}</Cell>
                    <Cell align="right">
                      <span className="inline-flex items-center justify-end gap-1.5">
                        {row.cargo_is_final ? null : <EstimateDot />}
                        {formatMoney(row.cost_cargo)}
                      </span>
                    </Cell>
                    <Cell
                      align="right"
                      className={negative ? "text-negative" : "text-positive-text"}
                    >
                      {formatMoney(row.profit)}
                    </Cell>
                    <Cell
                      align="right"
                      className={`pr-5 font-semibold ${negative ? "text-negative" : ""}`}
                    >
                      {formatPercent(row.margin_pct)}
                    </Cell>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {filtered.length === 0 ? (
            <p className="p-6 text-center text-cell text-ink-muted">{tr.sku.noResult}</p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-hairline bg-canvas px-5 py-2.5 text-helper text-ink-body">
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
        </div>
      </div>
    </div>
  );
}

function Head({
  children,
  align = "right",
  className = "",
}: {
  children: React.ReactNode;
  /** Hizalama prop'tur, sınıf üzerinden EZİLMEZ: `text-left`/`text-right` aynı
   *  özgüllükte olduğu için sınıf sırası değil CSS kaynak sırası kazanırdı. */
  align?: "left" | "right";
  className?: string;
}) {
  return (
    <th
      className={`sticky top-0 z-[5] border-b border-hairline bg-canvas px-3 py-2.5 ${
        align === "left" ? "text-left" : "text-right"
      } ${className}`}
    >
      <span className="col-head">{children}</span>
    </th>
  );
}

function Cell({
  children,
  align,
  className = "",
}: {
  children: React.ReactNode;
  align?: "right";
  className?: string;
}) {
  return (
    <td className={`px-3 py-2.5 ${align === "right" ? "text-right" : ""} ${className}`}>
      {children}
    </td>
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

function unique(values: string[]): string[] {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b, "tr-TR"));
}

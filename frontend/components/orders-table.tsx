"use client";

/**
 * Sipariş listesi tablosu — TanStack Table üzerinde (KVN-EK-08).
 *
 * Sipariş listesi kâr dökümüne giden kapıdır; "en çok zarar ettiren sipariş hangisi"
 * sorusu sıralanabilir kolon olmadan yanıtlanmıyordu. Sunum `DataGrid` deseninden gelir:
 * yapışkan başlık, sağa hizalı rakamlar, negatif satırda kırmızı zemin.
 */

import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";
import Link from "next/link";

import { type ColumnMeta, DataGrid } from "@/components/data-table";
import { EstimateBadge } from "@/components/ui";
import type { OrderRow } from "@/lib/api";
import { formatCount, formatDateTime, formatMoney, formatPercent, toNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

const STATUS_LABELS: Record<string, string> = tr.status;
const column = createColumnHelper<OrderRow>();

export function OrdersTable({ rows, brand }: { rows: OrderRow[]; brand: string }) {
  const columns = [
    column.accessor("external_order_id", {
      header: () => tr.table.order,
      cell: (info) => (
        <Link
          href={`/${brand}/orders/${info.row.original.order_id}`}
          className="font-mono text-micro text-ink-secondary underline decoration-ink-ghost underline-offset-4 hover:text-ink"
        >
          {info.getValue()}
        </Link>
      ),
      meta: { align: "left", edge: "start" } satisfies ColumnMeta,
    }),
    column.accessor("order_date", {
      header: () => tr.table.date,
      cell: (info) => <span className="text-ink-secondary">{formatDateTime(info.getValue())}</span>,
      meta: { align: "left" } satisfies ColumnMeta,
    }),
    column.accessor("store_name", {
      header: () => tr.table.store,
      cell: (info) => <span className="text-ink-secondary">{info.getValue()}</span>,
      meta: { align: "left" } satisfies ColumnMeta,
    }),
    column.accessor("status", {
      header: () => tr.table.status,
      cell: (info) => (
        <span className="text-ink-secondary">{STATUS_LABELS[info.getValue()] ?? info.getValue()}</span>
      ),
      meta: { align: "left" } satisfies ColumnMeta,
    }),
    column.accessor((row) => toNumber(row.gross_total), {
      id: "gross_total",
      header: () => tr.table.total,
      cell: (info) => formatMoney(info.getValue()),
      meta: { align: "right" } satisfies ColumnMeta,
    }),
    column.accessor((row) => toNumber(row.profit), {
      id: "profit",
      header: () => tr.table.profit,
      cell: (info) => (
        <span className={info.getValue() < 0 ? "text-negative" : "text-positive-text"}>
          {formatMoney(info.getValue())}
        </span>
      ),
      meta: { align: "right" } satisfies ColumnMeta,
    }),
    column.accessor((row) => toNumber(row.margin_pct), {
      id: "margin_pct",
      header: () => tr.table.margin,
      cell: (info) => (
        <span
          className={`font-semibold ${toNumber(info.row.original.profit) < 0 ? "text-negative" : ""}`}
        >
          {formatPercent(info.getValue())}
        </span>
      ),
      meta: { align: "right" } satisfies ColumnMeta,
    }),
    column.accessor("is_final", {
      header: () => tr.table.state,
      cell: (info) => <EstimateBadge isFinal={info.getValue()} />,
      enableSorting: false,
      meta: { align: "left", edge: "end" } satisfies ColumnMeta,
    }),
  ] as unknown as ColumnDef<OrderRow, unknown>[];

  return (
    <DataGrid
      data={rows}
      columns={columns}
      initialSorting={[{ id: "order_date", desc: true }]}
      rowKey={(row) => row.order_id}
      rowClassName={(row) => (toNumber(row.profit) < 0 ? "bg-negative-row" : "hover:bg-canvas")}
      maxHeight="640px"
      footer={<span>{tr.orders.footer.replace("{count}", formatCount(rows.length))}</span>}
    />
  );
}

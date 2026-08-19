"use client";

/**
 * Yoğun tablo kabuğu — TanStack Table + shadcn "DataTable" deseni (KVN-EK-08).
 *
 * Kolon tanımları veriyle birlikte gelir; bu bileşen yalnızca **sunumu** taşır:
 * yapışkan başlık, tıklanınca sıralayan kolon, `tabular-nums`, rakam kolonlarında sağa
 * hizalama ve satır vurgusu. Görsel karar tek yerde durduğu için yeni bir yoğun tablo
 * eklemek kolon tanımı yazmaktan ibaret.
 *
 * Sıralama **istemcide** yapılır: bu tablolar bir markanın dönem verisiyle sınırlı
 * (yüzlerce satır), sunucuya gidip gelmek gecikme katardı.
 */

import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react";
import { useState } from "react";

import tr from "@/locales/tr.json";

/** Kolon meta'sı: hizalama ve kenar boşluğu kolon tanımında yaşar. */
export type ColumnMeta = {
  align?: "left" | "right";
  /** İlk/son kolonun kart kenarına yaslanmaması için ekstra padding. */
  edge?: "start" | "end";
};

export function DataGrid<TData>({
  data,
  columns,
  initialSorting = [],
  rowClassName,
  rowKey,
  maxHeight = "560px",
  empty,
  footer,
}: {
  data: TData[];
  columns: ColumnDef<TData, unknown>[];
  initialSorting?: SortingState;
  rowClassName?: (row: TData) => string;
  rowKey?: (row: TData) => string;
  maxHeight?: string;
  empty?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const [sorting, setSorting] = useState<SortingState>(initialSorting);

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="overflow-hidden rounded-card border border-hairline bg-surface">
      <div className="overflow-auto" style={{ maxHeight }}>
        <table className="w-full border-collapse text-cell">
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => {
                  const meta = (header.column.columnDef.meta ?? {}) as ColumnMeta;
                  const sortable = header.column.getCanSort();
                  const direction = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      aria-sort={
                        direction === "asc"
                          ? "ascending"
                          : direction === "desc"
                            ? "descending"
                            : undefined
                      }
                      className={`sticky top-0 z-[5] border-b border-hairline bg-canvas px-3 py-2.5 ${
                        meta.align === "right" ? "text-right" : "text-left"
                      } ${meta.edge === "start" ? "pl-5" : ""} ${meta.edge === "end" ? "pr-5" : ""}`}
                    >
                      {sortable ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          title={direction === "asc" ? tr.sku.sortDesc : tr.sku.sortAsc}
                          className={`col-head inline-flex items-center gap-1 hover:text-ink-secondary ${
                            direction ? "text-ink-secondary" : ""
                          }`}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {direction === "asc" ? (
                            <ChevronUp className="h-3 w-3" aria-hidden />
                          ) : direction === "desc" ? (
                            <ChevronDown className="h-3 w-3" aria-hidden />
                          ) : (
                            <ChevronsUpDown className="h-3 w-3 text-ink-ghost" aria-hidden />
                          )}
                        </button>
                      ) : (
                        <span className="col-head">
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </span>
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={rowKey ? rowKey(row.original) : row.id}
                className={`border-b border-hairline ${
                  rowClassName?.(row.original) || "hover:bg-canvas"
                }`}
              >
                {row.getVisibleCells().map((cell) => {
                  const meta = (cell.column.columnDef.meta ?? {}) as ColumnMeta;
                  return (
                    <td
                      key={cell.id}
                      className={`px-3 py-2.5 ${meta.align === "right" ? "text-right" : ""} ${
                        meta.edge === "start" ? "pl-5" : ""
                      } ${meta.edge === "end" ? "pr-5" : ""}`}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>

        {table.getRowModel().rows.length === 0 ? empty : null}
      </div>

      {footer ? (
        <div className="flex flex-wrap items-center gap-3 border-t border-hairline bg-canvas px-5 py-2.5 text-helper text-ink-body">
          {footer}
        </div>
      ) : null}
    </div>
  );
}

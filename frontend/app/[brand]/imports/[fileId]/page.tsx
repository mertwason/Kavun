/**
 * İthalat dosyası detayı: masraf kalemleri, dağıtım önizlemesi, ödemeler (spec §12C.7-8).
 *
 * Dağıtım önizlemesi onaya kadar hiçbir şey yazmaz; onay ledger + WAC + maliyet
 * versiyonunu birlikte yazar.
 */

import { notFound } from "next/navigation";

import { ConfirmFileForm, CostItemForm, PaymentForm } from "@/components/import-forms";
import { KpiCard } from "@/components/kpi-card";
import { Card, DataTable, EmptyState, ErrorState, SectionHeader, Td, Th, TextLink, Tr } from "@/components/ui";
import { fetchImportFile } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatAmount, formatDate, formatMoney, formatRate, signClass } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

const ITEM_TYPES: Record<string, string> = tr.imports.itemTypes;

export default async function ImportFilePage({
  params,
}: {
  params: { brand: BrandSlug; fileId: string };
}) {
  const detail = await fetchImportFile(params.brand, params.fileId);
  if (!detail.ok && detail.status === 404) {
    notFound();
  }
  if (!detail.ok) {
    return (
      <Card>
        <ErrorState status={detail.status} />
      </Card>
    );
  }

  const { file, cost_items: items, lines, payments } = detail.data;
  const isConfirmed = file.status === "confirmed";

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-title font-medium">
          {file.file_no}
          <span className="ml-3 text-helper font-normal text-ink-muted">{detail.data.supplier_name}</span>
        </h1>
        <TextLink href={`/${params.brand}/imports`}>{tr.imports.backToList}</TextLink>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <KpiCard label={tr.imports.goodsTotal} value={formatMoney(detail.data.goods_total_try)} />
        <KpiCard label={tr.imports.costTotal} value={formatMoney(detail.data.cost_total_try)} />
        <KpiCard
          label={tr.imports.importVat}
          value={file.import_vat_paid === null ? "—" : formatMoney(file.import_vat_paid)}
          hint={tr.imports.importVatNote}
        />
        <KpiCard
          label={tr.imports.fxBeyanname}
          value={file.fx_rate_beyanname === null ? "—" : formatRate(file.fx_rate_beyanname)}
          hint={file.beyanname_date ? formatDate(file.beyanname_date) : undefined}
        />
      </div>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader
            title={tr.imports.allocation}
            subtitle={isConfirmed ? tr.imports.confirmed_ : tr.imports.allocationSubtitle}
          />
        </div>
        {lines.length === 0 ? (
          <EmptyState title={tr.empty.importLines} hint={tr.empty.importLinesHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.imports.line}</Th>
                <Th align="right">{tr.table.qty}</Th>
                <Th align="right">{tr.imports.goodsTotal}</Th>
                <Th align="right">{tr.imports.share}</Th>
                <Th align="right">{tr.imports.landedUnit}</Th>
              </>
            }
          >
            {lines.map((line) => (
              <Tr key={line.line_id}>
                <Td>{line.raw_text}</Td>
                <Td align="right">{formatAmount(line.qty)}</Td>
                <Td align="right">{formatMoney(line.goods_total_try)}</Td>
                <Td align="right">{formatMoney(line.extra_share_try)}</Td>
                <Td align="right">{formatMoney(line.landed_unit_cost_try)}</Td>
              </Tr>
            ))}
          </DataTable>
        )}
        <div className="border-t border-hairline p-5">
          <ConfirmFileForm
            brand={params.brand}
            fileId={params.fileId}
            disabled={isConfirmed || lines.length === 0}
          />
        </div>
      </Card>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.imports.costItems} subtitle={tr.imports.costItemsSubtitle} />
        </div>
        {items.length === 0 ? (
          <EmptyState title={tr.imports.costItems} hint={tr.imports.costItemsSubtitle} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.imports.itemType}</Th>
                <Th align="right">{tr.imports.amount}</Th>
                <Th>{tr.imports.currency}</Th>
                <Th align="right">{tr.imports.amountTry}</Th>
                <Th>{tr.imports.vendor}</Th>
              </>
            }
          >
            {items.map((item) => (
              <Tr key={item.id}>
                <Td>{ITEM_TYPES[item.item_type] ?? item.item_type}</Td>
                <Td align="right">{formatAmount(item.amount_original)}</Td>
                <Td>{item.currency}</Td>
                <Td align="right">{formatMoney(item.amount_try)}</Td>
                <Td className="text-ink-muted">{item.vendor ?? "—"}</Td>
              </Tr>
            ))}
          </DataTable>
        )}
        <div className="border-t border-hairline p-5">
          <CostItemForm brand={params.brand} fileId={params.fileId} disabled={isConfirmed} />
        </div>
      </Card>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.imports.payments} subtitle={tr.imports.paymentsSubtitle} />
        </div>
        {payments.length === 0 ? (
          <EmptyState title={tr.imports.payments} hint={tr.imports.paymentsSubtitle} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.imports.payDate}</Th>
                <Th align="right">{tr.imports.payAmount}</Th>
                <Th>{tr.imports.currency}</Th>
                <Th align="right">{tr.imports.payRate}</Th>
                <Th align="right">{tr.imports.fxDiff}</Th>
              </>
            }
          >
            {payments.map((payment) => (
              <Tr key={payment.id}>
                <Td className="text-ink-muted">{formatDate(payment.pay_date)}</Td>
                <Td align="right">{formatAmount(payment.amount_original)}</Td>
                <Td>{payment.currency}</Td>
                <Td align="right">{formatRate(payment.fx_rate_payment)}</Td>
                <Td align="right" className={signClass(payment.fx_diff_try ?? 0)}>
                  {payment.fx_diff_try === null ? "—" : formatMoney(payment.fx_diff_try)}
                </Td>
              </Tr>
            ))}
          </DataTable>
        )}
        <div className="border-t border-hairline p-5">
          <PaymentForm brand={params.brand} fileId={params.fileId} />
        </div>
      </Card>
    </>
  );
}

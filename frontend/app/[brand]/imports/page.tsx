/**
 * İthalat dosyaları listesi + açık döviz pozisyonu (spec §12C.7-8).
 *
 * Modül bayrağı kapalı markada API 404 döner; ekran bunu "kapalı modül" olarak gösterir,
 * hata gibi değil (spec §3A.4).
 */

import Link from "next/link";

import { Card, DataTable, EmptyState, ErrorState, SectionHeader, Td, Th, Tr } from "@/components/ui";
import { fetchFxExposure, fetchImportFiles } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatAmount, formatDate, formatMoney, formatRate, signClass } from "@/lib/format";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function ImportsPage({ params }: { params: { brand: BrandSlug } }) {
  const [files, exposure] = await Promise.all([
    fetchImportFiles(params.brand),
    fetchFxExposure(params.brand),
  ]);

  if (!files.ok && files.status === 404) {
    return (
      <>
        <h1 className="text-title font-medium">{tr.imports.title}</h1>
        <Card>
          <EmptyState title={tr.imports.disabled} hint={tr.imports.disabledHint} />
        </Card>
      </>
    );
  }

  return (
    <>
      <h1 className="text-title font-medium">{tr.imports.title}</h1>
      <p className="-mt-4 text-helper text-ink-muted">{tr.imports.subtitle}</p>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.imports.fxExposure} subtitle={tr.imports.paymentsSubtitle} />
        </div>
        {!exposure.ok || exposure.data.length === 0 ? (
          <EmptyState title={tr.empty.imports} hint={tr.empty.importsHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.imports.currency}</Th>
                <Th align="right">{tr.imports.openAmount}</Th>
                <Th align="right">{tr.imports.paidAmount}</Th>
                <Th align="right">{tr.imports.costRate}</Th>
                <Th align="right">{tr.imports.realized}</Th>
              </>
            }
          >
            {exposure.data.map((row) => (
              <Tr key={row.currency}>
                <Td>{row.currency}</Td>
                <Td align="right">{formatAmount(row.open_amount)}</Td>
                <Td align="right">{formatAmount(row.paid_amount)}</Td>
                <Td align="right">{row.cost_fx_rate === null ? "—" : formatRate(row.cost_fx_rate)}</Td>
                <Td align="right" className={signClass(row.realized_fx_diff_try)}>
                  {formatMoney(row.realized_fx_diff_try)}
                </Td>
              </Tr>
            ))}
          </DataTable>
        )}
      </Card>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.imports.title} />
        </div>
        {!files.ok ? (
          <ErrorState status={files.status} />
        ) : files.data.length === 0 ? (
          <EmptyState title={tr.empty.imports} hint={tr.empty.importsHint} />
        ) : (
          <DataTable
            head={
              <>
                <Th>{tr.imports.fileNo}</Th>
                <Th>{tr.imports.beyanname}</Th>
                <Th>{tr.imports.beyannameDate}</Th>
                <Th>{tr.imports.currency}</Th>
                <Th align="right">{tr.imports.fxBeyanname}</Th>
                <Th align="right">{tr.imports.importVat}</Th>
                <Th>{tr.imports.status}</Th>
              </>
            }
          >
            {files.data.map((file) => (
              <Tr key={file.id}>
                <Td>
                  <Link
                    href={`/${params.brand}/imports/${file.id}`}
                    className="underline underline-offset-4"
                  >
                    {file.file_no}
                  </Link>
                </Td>
                <Td className="font-mono text-helper text-ink-muted">{file.beyanname_no ?? "—"}</Td>
                <Td className="text-ink-muted">
                  {file.beyanname_date ? formatDate(file.beyanname_date) : "—"}
                </Td>
                <Td>{file.currency}</Td>
                <Td align="right">
                  {file.fx_rate_beyanname === null ? "—" : formatRate(file.fx_rate_beyanname)}
                </Td>
                <Td align="right" className="text-ink-muted">
                  {file.import_vat_paid === null ? "—" : formatMoney(file.import_vat_paid)}
                </Td>
                <Td>{file.status === "confirmed" ? tr.imports.confirmed : tr.imports.open}</Td>
              </Tr>
            ))}
          </DataTable>
        )}
        <p className="px-5 pb-4 text-helper text-ink-muted">{tr.imports.importVatNote}</p>
      </Card>
    </>
  );
}

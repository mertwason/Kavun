/**
 * SKU marj listesi — handoff `SKU Marjlari.dc.html` (spec §10.2).
 *
 * Dönem seçimi URL'de (paylaşılabilir), arama/kanal/kategori/negatif filtreleri ise
 * tabloda canlı çalışır — sunucuya gidip gelmeden daralır.
 */

import { DEFAULT_DAYS, PeriodPicker, periodRange, resolveDays } from "@/components/period-picker";
import { SkuTable } from "@/components/sku-table";
import { Card, EmptyState, ErrorState } from "@/components/ui";
import { fetchSkuMargins } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function SkuMarginsPage({
  params,
  searchParams,
}: {
  params: { brand: BrandSlug };
  searchParams: { days?: string };
}) {
  const days = resolveDays(searchParams.days ?? String(DEFAULT_DAYS));
  const result = await fetchSkuMargins(params.brand, periodRange(days));

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="sr-only">{tr.nav.skuMargins}</h1>
        <span />
        <PeriodPicker basePath={`/${params.brand}/sku`} activeDays={days} />
      </div>

      {!result.ok ? (
        <Card>
          <ErrorState status={result.status} />
        </Card>
      ) : result.data.length === 0 ? (
        <Card>
          <EmptyState title={tr.empty.sku} hint={tr.empty.skuHint} />
        </Card>
      ) : (
        <SkuTable rows={result.data} />
      )}
    </>
  );
}

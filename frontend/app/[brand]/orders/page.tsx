/** Sipariş listesi — kâr dökümü ekranının giriş kapısı (spec §10.3). */

import { OrdersTable } from "@/components/orders-table";
import { DEFAULT_DAYS, PeriodPicker, periodRange, resolveDays } from "@/components/period-picker";
import { Card, EmptyState, ErrorState } from "@/components/ui";
import { fetchOrders } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function OrdersPage({
  params,
  searchParams,
}: {
  params: { brand: BrandSlug };
  searchParams: { days?: string };
}) {
  const days = resolveDays(searchParams.days ?? String(DEFAULT_DAYS));
  const result = await fetchOrders(params.brand, periodRange(days));

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="sr-only">{tr.nav.orders}</h1>
        <span />
        <PeriodPicker basePath={`/${params.brand}/orders`} activeDays={days} />
      </div>

      {!result.ok ? (
        <Card>
          <ErrorState status={result.status} />
        </Card>
      ) : result.data.length === 0 ? (
        <Card>
          <EmptyState title={tr.empty.orders} hint={tr.empty.ordersHint} />
        </Card>
      ) : (
        <OrdersTable rows={result.data} brand={params.brand} />
      )}
    </>
  );
}

/**
 * Ayarlar ekranı (spec §10.7).
 *
 * Gerçek veriye geçişin kapısı: mağaza tanımlanır, bağlantı bilgileri şifreli kasaya
 * yazılır, hizmet bedeli ve kargo tarifesi burada yönetilir. Credential içeriği hiçbir
 * yanıtta dönmez — ekran yalnızca "kayıtlı mı, ne zaman güncellendi" bilgisini gösterir.
 */

import { CargoTariffPanel } from "@/components/cargo-tariff-panel";
import { StoreList } from "@/components/store-settings";
import { Card, EmptyState, SectionHeader } from "@/components/ui";
import { fetchCargoTariffs, fetchStores } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function SettingsPage({ params }: { params: { brand: BrandSlug } }) {
  const [stores, tariffs] = await Promise.all([
    fetchStores(params.brand),
    fetchCargoTariffs(params.brand),
  ]);

  return (
    <>
      <h1 className="text-lg font-medium">{tr.settings.title}</h1>
      <p className="-mt-4 text-xs text-ink-faint">{tr.settings.subtitle}</p>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.settings.storesTitle} subtitle={tr.settings.storesSubtitle} />
        {stores.ok && stores.data.length === 0 ? (
          <EmptyState title={tr.settings.noStores} hint={tr.settings.noStoresHint} />
        ) : (
          <StoreList brand={params.brand} stores={stores.ok ? stores.data : []} />
        )}
      </Card>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.settings.tariffTitle} subtitle={tr.settings.tariffSubtitle} />
        <CargoTariffPanel brand={params.brand} tariffs={tariffs.ok ? tariffs.data : []} />
      </Card>
    </>
  );
}

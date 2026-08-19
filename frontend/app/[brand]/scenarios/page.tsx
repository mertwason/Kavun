/** Senaryolar ekranı — karşılaştırma + hedef marj çözücü (spec §12A.4, §12A.5). */

import { ScenarioWorkbench } from "@/components/scenario-workbench";
import { Card, EmptyState, ErrorState, SectionHeader } from "@/components/ui";
import { fetchPriceRows, fetchScenarios } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function ScenariosPage({ params }: { params: { brand: BrandSlug } }) {
  const [rows, saved] = await Promise.all([
    fetchPriceRows(params.brand),
    fetchScenarios(params.brand),
  ]);

  if (!rows.ok) {
    return (
      <Card>
        <ErrorState status={rows.status} />
      </Card>
    );
  }

  // Aynı ürün birden fazla kanalda listeleniyor; senaryo ürün bazlıdır.
  const products = rows.data.filter(
    (row, index, all) => all.findIndex((item) => item.product_id === row.product_id) === index,
  );

  return (
    <>
      <h1 className="text-lg font-medium">{tr.nav.scenarios}</h1>
      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.scenarios.title} subtitle={tr.scenarios.subtitle} />
        {products.length === 0 ? (
          <EmptyState title={tr.empty.scenarios} hint={tr.empty.scenariosHint} />
        ) : (
          <ScenarioWorkbench
            brand={params.brand}
            products={products}
            saved={saved.ok ? saved.data : []}
          />
        )}
      </Card>
    </>
  );
}

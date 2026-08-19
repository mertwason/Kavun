/** Yeni Ürün Değerlendir + taslak listesi (spec §12A.3, §12A.5). */

import { DraftForm } from "@/components/draft-form";
import { DraftList } from "@/components/draft-list";
import { Card, EmptyState, ErrorState, SectionHeader } from "@/components/ui";
import { fetchDrafts } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function DraftsPage({ params }: { params: { brand: BrandSlug } }) {
  const result = await fetchDrafts(params.brand);

  return (
    <>
      <h1 className="text-lg font-medium">{tr.nav.drafts}</h1>

      <Card className="flex flex-col gap-4 p-5">
        <SectionHeader title={tr.drafts.formTitle} subtitle={tr.drafts.formSubtitle} />
        <DraftForm brand={params.brand} />
      </Card>

      <Card className="flex flex-col">
        <div className="p-5 pb-2">
          <SectionHeader title={tr.drafts.listTitle} />
        </div>
        {!result.ok ? (
          <ErrorState status={result.status} />
        ) : result.data.length === 0 ? (
          <EmptyState title={tr.empty.drafts} hint={tr.empty.draftsHint} />
        ) : (
          <DraftList brand={params.brand} drafts={result.data} />
        )}
      </Card>
    </>
  );
}

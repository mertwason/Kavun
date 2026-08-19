/**
 * SKU marj listesi indirme köprüsü.
 *
 * Ekrandaki filtreler sorgu dizesiyle taşınır: indirilen dosya, o an bakılan listeyle
 * aynı olsun — "ekranda gördüğüm 12 satır, dosyada 200 satır" şaşkınlığı olmasın.
 */

import { downloadSkuMargins } from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";

export const dynamic = "force-dynamic";

const ALLOWED = ["from", "to", "category", "only_negative", "limit"];

export async function GET(request: Request, { params }: { params: { brand: string } }) {
  if (!isBrandSlug(params.brand)) {
    return new Response("Bulunamadı", { status: 404 });
  }

  // Yalnızca bilinen parametreler geçirilir; gelişigüzel sorgu API'ye taşınmaz.
  const incoming = new URL(request.url).searchParams;
  const query = new URLSearchParams();
  for (const key of ALLOWED) {
    const value = incoming.get(key);
    if (value) query.set(key, value);
  }

  const result = await downloadSkuMargins(params.brand, query.toString());
  if (!result.ok) {
    return new Response("SKU listesi alınamadı", { status: result.status || 502 });
  }

  return new Response(result.body, {
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": `attachment; filename="${result.filename}"`,
    },
  });
}

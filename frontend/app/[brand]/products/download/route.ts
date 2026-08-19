/**
 * Fiyat listesi indirme köprüsü.
 *
 * Tarayıcı API token'ını taşıyamaz (token sunucu tarafında kalır, tasarım gereği);
 * bu yüzden indirme isteği Next sunucusundan geçer.
 */

import { downloadPriceList } from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: { brand: string } }) {
  if (!isBrandSlug(params.brand)) {
    return new Response("Bulunamadı", { status: 404 });
  }

  const result = await downloadPriceList(params.brand);
  if (!result.ok) {
    return new Response("Fiyat listesi alınamadı", { status: result.status || 502 });
  }

  return new Response(result.body, {
    headers: {
      "Content-Type":
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": `attachment; filename="${result.filename}"`,
    },
  });
}

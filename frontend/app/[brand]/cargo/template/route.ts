/** Kargo faturası şablonu indirme köprüsü (token sunucuda kalır). */

import { downloadCargoTemplate } from "@/lib/api";
import { isBrandSlug } from "@/lib/brands";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: { brand: string } }) {
  if (!isBrandSlug(params.brand)) {
    return new Response("Bulunamadı", { status: 404 });
  }

  const result = await downloadCargoTemplate(params.brand);
  if (!result.ok) {
    return new Response("Şablon alınamadı", { status: result.status || 502 });
  }

  return new Response(result.body, {
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": `attachment; filename="${result.filename}"`,
    },
  });
}

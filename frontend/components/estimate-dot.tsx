/**
 * "Tahmini" göstergesi — ürünün DNA'sı (handoff, Uygulama İskeleti).
 *
 * Kesinleşmemiş her rakamın yanında 6px amber nokta durur ve hover'da sebebini söyler.
 * **Hücre seviyesinde görünür, asla yalnız tooltip'te değil:** nokta olmadan tooltip
 * gösterilse kullanıcı hangi rakamın tahmini olduğunu keşfedemezdi.
 */

import tr from "@/locales/tr.json";

export function EstimateDot({ title = tr.dashboard.estimatedTip }: { title?: string }) {
  return (
    <span
      title={title}
      aria-label={title}
      className="inline-block h-1.5 w-1.5 shrink-0 rounded-pill bg-estimated"
    />
  );
}

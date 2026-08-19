/**
 * Kaynak rozeti — handoff `Siparis Detayi.dc.html`, Kalem Dökümü.
 *
 * Her kalemin nereden geldiğini söyler: API, tarife, hakediş, fatura, hesaplanan ya da
 * desi tahmini. **Tahmini olan amber**, hesaplanan mavi, kesin olanlar nötr — renk burada
 * "güvenilirlik" anlamı taşır, dekorasyon değil.
 */

import { EstimateDot } from "@/components/estimate-dot";
import tr from "@/locales/tr.json";

export type SourceKind = keyof typeof tr.source;

const TONES: Record<string, string> = {
  desi: "border-estimated-border bg-estimated-tint text-estimated-text",
  hesaplanan: "border-info-border bg-info-tint text-info",
};

export function SourceBadge({ kind }: { kind: SourceKind }) {
  const tone = TONES[kind] ?? "border-hairline bg-divider text-ink-secondary";
  return (
    <span className={`badge ${tone}`}>
      {kind === "desi" ? <EstimateDot /> : null}
      {tr.source[kind]}
    </span>
  );
}

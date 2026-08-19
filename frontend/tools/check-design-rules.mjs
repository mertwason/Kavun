/**
 * Tasarım kuralları denetimi — `docs/KAVUN_Design_Brief.md` "Yapılmayacaklar" listesi
 * ve handoff'un gölge kuralı (KVN-EK-08).
 *
 * Brief bir belge olarak duruyordu; ihlali ancak gözle yakalanıyordu. Bu betik listeyi
 * **çalıştırılabilir** hâle getirir: koyu tema sınıfı, gradyan, cam/blur efekti, emoji
 * tabanlı durum göstergesi ve handoff'ta tanımlı olmayan gölge eklendiği anda CI kırılır.
 *
 * Bilinçli istisna için `design-allow: <gerekçe>` işareti konur — para/float kuralındaki
 * (`backend/tools/check_money_float.py`) kalıbın aynısı. İşaret ihlalin bulunduğu satırda
 * ya da onu **önceleyen dört satırda** olabilir: JSX'te `className` satırının sonuna
 * yorum yazılamıyor, gerekçe doğal olarak bir üstteki blok yorumuna düşüyor.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const SCAN_DIRS = ["app", "components", "lib"];
const SCAN_EXT = new Set([".ts", ".tsx", ".css"]);
const ALLOW = /design-allow:/;
/** İşaretin ihlalden kaç satır önce durabileceği (JSX'te gerekçe blok yorumuna düşer). */
const ALLOW_WINDOW = 4;

/** Handoff yalnızca üç gölgeye izin veriyor; hepsi Tailwind config'inde adlandırılmış. */
const ALLOWED_SHADOW_CLASSES = new Set([
  "shadow-modal",
  "shadow-panel",
  "shadow-tooltip",
  "shadow-none",
]);

const RULES = [
  {
    id: "koyu-tema",
    test: /(^|[\s"'`])dark:/,
    message: "Koyu tema v1'de yok (brief: Yapılmayacaklar).",
  },
  {
    id: "gradyan",
    test: /bg-gradient-|linear-gradient|radial-gradient/,
    message: "Gradyan zemin yok — zemin kırık beyaz, kart saf beyaz.",
  },
  {
    id: "cam-efekti",
    test: /backdrop-blur|\bblur-(sm|md|lg|xl|\[)/,
    message: "Cam/blur efekti yok.",
  },
  {
    id: "emoji-durum",
    // Durum göstergesi olarak emoji: renkli semboller ve işaretler.
    test: /[\u{1F300}-\u{1FAFF}\u{2705}\u{274C}\u{26A0}\u{2B50}]/u,
    message: "Emoji tabanlı durum göstergesi yok — rozet/ikon kullanılır.",
  },
];

/** `shadow-[...]` ve `shadow-md` gibi Tailwind gölge sınıfları. */
const SHADOW_CLASS = /\bshadow-(?!modal\b|panel\b|tooltip\b|none\b)[a-z0-9[\]/.,()#-]+/gi;

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      yield* walk(full);
    } else if (SCAN_EXT.has(extname(entry))) {
      yield full;
    }
  }
}

const violations = [];

for (const dir of SCAN_DIRS) {
  for (const file of walk(join(ROOT, dir))) {
    const lines = readFileSync(file, "utf8").split("\n");
    lines.forEach((line, index) => {
      const window = lines.slice(Math.max(0, index - ALLOW_WINDOW), index + 1).join("\n");
      if (ALLOW.test(window)) return;
      const where = `${relative(ROOT, file)}:${index + 1}`;

      for (const rule of RULES) {
        if (rule.test.test(line)) {
          violations.push(`${where}: ${rule.message} [${rule.id}]`);
        }
      }

      for (const match of line.matchAll(SHADOW_CLASS)) {
        if (!ALLOWED_SHADOW_CLASSES.has(match[0])) {
          violations.push(
            `${where}: "${match[0]}" — handoff yalnızca modal/panel/tooltip gölgesine izin veriyor. [golge]`,
          );
        }
      }
    });
  }
}

if (violations.length > 0) {
  console.error(violations.join("\n"));
  console.error(`\n${violations.length} tasarım kuralı ihlali (Design Brief · Yapılmayacaklar).`);
  process.exit(1);
}

console.log("Tasarım kuralları temiz.");

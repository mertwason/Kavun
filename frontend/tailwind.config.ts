import type { Config } from "tailwindcss";

/**
 * Tasarım tokenları — KAVUN_Design_Brief.md bağlayıcıdır:
 * açık tema, kırık beyaz zemin, saf beyaz kart, 1px hairline ayrım,
 * anlam taşıyan renk yalnızca veri için (pozitif/negatif/tahmini).
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#FAFAF9",
        surface: "#FFFFFF",
        hairline: "#E7E5E4",
        ink: {
          DEFAULT: "#1C1917",
          muted: "#57534E",
          faint: "#A8A29E",
        },
        // Veri anlamı taşıyan renkler
        positive: "#15803D",
        negative: "#B91C1C",
        estimated: "#B45309",
        // Marka aksanları (workspace bazlı — bkz. brief)
        alessi: "#C8102E",
        kahveji: "#A16207",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        kpi: ["2.25rem", { lineHeight: "2.5rem", fontWeight: "500" }],
      },
      borderRadius: {
        card: "0.625rem",
      },
      boxShadow: {
        // Gölge yalnızca modal/popover'da kullanılır.
        overlay: "0 8px 32px rgba(28, 25, 23, 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;

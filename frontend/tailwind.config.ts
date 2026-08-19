import type { Config } from "tailwindcss";

/**
 * Tasarım tokenları — `docs/design_handoff_kavun/README.md` **bağlayıcıdır** (KVN-EK-08).
 *
 * Açık tema, kırık beyaz zemin, saf beyaz kart, 1px hairline ayrım. Semantik renk
 * YALNIZCA veri anlamı taşır (pozitif/negatif/tahmini/bilgi); workspace aksanı ise
 * yalnızca üç yerde görünür: aktif nav öğesinin sol çizgisi+metni, birincil buton,
 * workspace rozeti. Başka hiçbir yerde.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#FAFAF9",
        surface: "#FFFFFF",
        hairline: "#E7E5E4",
        divider: "#F5F5F4",
        ink: {
          DEFAULT: "#1C1917",
          secondary: "#57534E",
          body: "#78716C",
          muted: "#A8A29E",
          ghost: "#D6D3D1",
          // Geriye dönük adlar (mevcut ekranlar bunları kullanıyor).
          faint: "#A8A29E",
        },
        // --- semantik: yalnızca veri anlamı ---
        positive: {
          DEFAULT: "#16A34A",
          text: "#15803D",
          tint: "#F0FDF4",
          border: "#BBF7D0",
        },
        negative: {
          DEFAULT: "#DC2626",
          tint: "#FEF2F2",
          border: "#FECACA",
          row: "#FEF7F7",
        },
        estimated: {
          DEFAULT: "#D97706",
          text: "#B45309",
          tint: "#FFFBEB",
          border: "#FDE68A",
        },
        info: {
          DEFAULT: "#2563EB",
          tint: "#EFF6FF",
          border: "#DBEAFE",
        },
        // --- workspace aksanları ---
        kahveji: { DEFAULT: "#B45309", hover: "#92400E" },
        alessi: { DEFAULT: "#C8102E", hover: "#A00D25" },
        holding: { DEFAULT: "#292524", hover: "#1C1917" },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        // Handoff ölçeği — gövde 14, ikincil/hücre 13, yardımcı 12–12.5, mikro 11.
        micro: ["11px", { lineHeight: "1.4" }],
        helper: ["12px", { lineHeight: "1.45" }],
        cell: ["13px", { lineHeight: "1.45" }],
        body: ["14px", { lineHeight: "1.5" }],
        title: ["15px", { lineHeight: "1.4", fontWeight: "600" }],
        // Kolon başlığı: 10.5px/600 uppercase, letter-spacing 0.06em.
        column: ["10.5px", { lineHeight: "1.2", letterSpacing: "0.06em", fontWeight: "600" }],
        kpi: ["30px", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "600" }],
        kpiSm: ["17px", { lineHeight: "1.2", fontWeight: "600" }],
      },
      borderRadius: {
        card: "10px",
        exec: "12px",
        control: "8px",
        pill: "999px",
      },
      spacing: {
        sidebar: "240px",
        topbar: "56px",
      },
      maxWidth: {
        content: "1360px",
      },
      boxShadow: {
        // Gölge yok — yalnızca bu üçü (handoff).
        modal: "0 16px 40px rgba(28,25,23,0.16)",
        panel: "-12px 0 32px rgba(28,25,23,0.1)",
        tooltip: "0 4px 12px rgba(0,0,0,0.15)",
      },
    },
  },
  plugins: [],
};

export default config;

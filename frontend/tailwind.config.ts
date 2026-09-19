import type { Config } from "tailwindcss";
/**
 * NovaShip Averis theme: orange and white.
 * One accent (orange), warm stone neutrals, white surfaces.
 * Semantic colours stay meaningful: match = green, mismatch = red, review = amber (yellow-leaning so it never reads as the orange accent).
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 900: "#1b1a18", 800: "#292724", 700: "#494640", 600: "#625e57", 500: "#7b766e", 400: "#a7a198", 300: "#d8d2c9", 200: "#e9e4dc", 100: "#f3f0eb", 50: "#faf8f4" },
        accent: { DEFAULT: "#f36c13", hover: "#cf5608", bg: "#fff0e5", soft: "#ffe4cc", fg: "#a94308", ring: "#f4b78b" },
        match: { DEFAULT: "#25804b", bg: "#e8f5ec", fg: "#155b32" },
        mismatch: { DEFAULT: "#bd4b3b", bg: "#fff0ed", fg: "#8c3026" },
        review: { DEFAULT: "#a87117", bg: "#fff6de", fg: "#79520f" },
      },
      boxShadow: {
        card: "0 1px 2px rgba(35,30,24,0.03), 0 10px 28px rgba(54,42,28,0.055)",
        glow: "0 12px 32px rgba(243,108,19,0.18)",
      },
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
    },
  },
  plugins: [],
};
export default config;

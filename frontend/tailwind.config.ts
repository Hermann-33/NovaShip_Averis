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
        ink: { 900: "#1c1917", 800: "#292524", 700: "#44403c", 600: "#57534e", 500: "#78716c", 400: "#a8a29e", 300: "#d6d3d1", 200: "#e7e5e4", 100: "#f5f5f4", 50: "#fafaf9" },
        accent: { DEFAULT: "#ea580c", hover: "#c2410c", bg: "#fff1e6", soft: "#ffedd5", fg: "#9a3412", ring: "#fdba74" },
        match: { DEFAULT: "#16a34a", bg: "#dcfce7", fg: "#14532d" },
        mismatch: { DEFAULT: "#dc2626", bg: "#fee2e2", fg: "#7f1d1d" },
        review: { DEFAULT: "#ca8a04", bg: "#fef9c3", fg: "#713f12" },
      },
      boxShadow: {
        card: "0 1px 2px rgba(28,25,23,0.04), 0 4px 16px rgba(234,88,12,0.06)",
        glow: "0 8px 30px rgba(234,88,12,0.18)",
      },
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
    },
  },
  plugins: [],
};
export default config;

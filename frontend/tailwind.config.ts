import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Local CJK",
          "Microsoft YaHei",
          "Noto Sans CJK SC",
          "Source Han Sans SC",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: ["Cascadia Code", "Local CJK", "Consolas", "monospace"],
      },
      colors: {
        surface: "#f3f6f4",
        panel: "#ffffff",
        line: "rgba(20, 31, 45, 0.12)",
        ink: {
          900: "#111827",
          700: "#39465a",
          600: "#4b5565",
          500: "#667085",
          400: "#98a2b3",
        },
      },
      borderRadius: {
        ui: "8px",
      },
      boxShadow: {
        panel: "0 1px 2px rgba(17, 24, 39, 0.06), 0 10px 28px rgba(17, 24, 39, 0.05)",
        lift: "0 14px 36px rgba(17, 24, 39, 0.10)",
      },
    },
  },
  plugins: [],
} satisfies Config;

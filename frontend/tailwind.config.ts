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
        surface: "#f5f7fb",
        panel: "#ffffff",
        line: "rgba(15, 23, 42, 0.10)",
        ink: {
          900: "#182033",
          700: "#445066",
          500: "#687386",
        },
      },
      borderRadius: {
        ui: "6px",
      },
    },
  },
  plugins: [],
} satisfies Config;

import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
      colors: {
        page: "#f4f4f2",
        surface: "#ffffff",
        subtle: "#fafaf8",
        gutter: "#f7f7f5",
        muted: "#ededea",
        track: "#e6e6e2",
        line: { DEFAULT: "#d6d6d2", strong: "#c9c9c5", subtle: "#e6e6e2", faint: "#ededea" },
        ink: {
          DEFAULT: "#262624",
          secondary: "#55554f",
          tertiary: "#4a4a46",
          subtle: "#3a3a36",
          disabled: "#8a8a84",
        },
        link: { DEFAULT: "#2f5fa8", hover: "#1f4580" },
        info: { bg: "#e3ecf8", fg: "#1f4580" },
        error: { bg: "#fbe3df", fg: "#7a1f12", line: "#fdf0ee", strong: "#a3311f" },
        focus: { ring: "#6b8fc9" },
      },
      opacity: { disabled: "0.55" },
      // Type scale from tokens.md "Typography".
      fontSize: {
        title: "24px",
        "title-sm": "22px",
        section: "15px",
        body: "14px",
        small: "13px",
        caption: "12px",
        micro: "11px",
      },
      // Odd steps from tokens.md "Spacing" (18px and 22px).
      spacing: { "4.5": "18px", "5.5": "22px" },
      borderRadius: { xs: "3px", sm: "4px", md: "6px", lg: "8px", xl: "10px", "2xl": "12px" },
      maxWidth: { content: "1376px", page: "640px" },
      boxShadow: { page: "0 1px 3px rgb(0 0 0 / 0.12)", toast: "0 4px 16px rgb(0 0 0 / 0.18)" },
    },
  },
  plugins: [],
} satisfies Config;

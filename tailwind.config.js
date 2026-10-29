/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Observer Strict Palette
        ivory: {
          DEFAULT: "var(--bg-ivory, #F5F2E9)",
          subtle: "var(--bg-ivory-subtle, #EFECE2)",
        },
        panel: {
          DEFAULT: "var(--panel-white, #FFFFFF)",
        },
        sage: {
          DEFAULT: "var(--primary-sage, #496B5A)",
          hover: "var(--primary-sage-hover, #3D594B)",
          pale: "var(--highlight-pale, #DCE5D8)",
          paleHover: "var(--highlight-pale-hover, #CFDCC9)",
        },
        ink: {
          DEFAULT: "var(--text-ink, #293B32)",
          muted: "var(--text-ink-muted, #4A6356)",
          subtle: "var(--text-ink-subtle, #6E887B)",
        },
        clay: {
          DEFAULT: "var(--accent-clay, #B87559)",
          pale: "var(--accent-clay-pale, #F2E4DE)",
        },
      },
      fontFamily: {
        sans: ["'Atkinson Hyperlegible'", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
      borderRadius: {
        card: "1rem",
        button: "0.625rem",
      },
      boxShadow: {
        calm: "0 2px 8px -2px rgba(41, 59, 50, 0.05), 0 4px 16px -4px rgba(41, 59, 50, 0.08)",
        floating: "0 6px 24px -4px rgba(41, 59, 50, 0.12)",
      },
    },
  },
  plugins: [],
};

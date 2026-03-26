/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#ffffff",
        surface: "#f5f5f7",
        border: "rgba(0, 0, 0, 0.08)",
        accent: "#0071e3",
        muted: "#86868b",
        error: "#ff3b30",
        warning: "#ff9f0a",
        success: "#30d158",
      },
      fontFamily: {
        sans: [
          "Manrope",
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Display",
          "Segoe UI",
          "Helvetica Neue",
          "sans-serif",
        ],
      },
      borderRadius: {
        apple: "0.875rem",
        "apple-lg": "1.25rem",
      },
      boxShadow: {
        apple: "0 2px 8px rgba(0, 0, 0, 0.04)",
        "apple-md": "0 4px 16px rgba(0, 0, 0, 0.06)",
        "apple-lg": "0 12px 40px rgba(0, 0, 0, 0.08)",
      },
    },
  },
  plugins: [],
};

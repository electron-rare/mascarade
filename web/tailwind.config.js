/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#000000",
        surface: "#070707",
        border: "#1b4d2c",
        accent: "#ffd166",
        muted: "#c4a86b",
        error: "#ff3b5c",
        warning: "#ccff00",
      },
    },
  },
  plugins: [],
};

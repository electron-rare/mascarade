/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const base = env.CRAZY_LIFE_BASE || "/";
  const proxyTarget = env.CRAZY_LIFE_API_ORIGIN || "http://localhost:3100";

  return {
    base,
    plugins: [react()],
    build: {
      outDir: "dist",
      emptyOutDir: true,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ["react", "react-dom", "react-router-dom"],
            editor: ["@monaco-editor/react"],
            flow: ["@xyflow/react", "dagre"],
          },
        },
      },
    },
    server: {
      port: 80,
      proxy: {
        "/api": proxyTarget,
        "/health": proxyTarget,
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
    },
  };
});

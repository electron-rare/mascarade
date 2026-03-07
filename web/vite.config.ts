import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const base = env.CRAZY_LIFE_BASE || "/";
  const proxyTarget = env.CRAZY_LIFE_API_ORIGIN || "http://localhost:3000";
  const outDir = existsSync(resolve(process.cwd(), "../api/package.json"))
    ? "../api/public"
    : "dist";

  return {
    base,
    plugins: [react()],
    build: {
      outDir,
      emptyOutDir: true,
    },
    server: {
      port: 80,
      proxy: {
        "/api": proxyTarget,
        "/health": proxyTarget,
      },
    },
  };
});

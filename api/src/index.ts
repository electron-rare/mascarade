import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { Hono } from "hono";
import { logger } from "hono/logger";
import { existsSync } from "node:fs";
import { authMiddleware } from "./middleware/auth.js";
import { health } from "./routes/health.js";
import { agents } from "./routes/agents.js";
import { notion } from "./routes/notion.js";
import { comfyui } from "./routes/comfyui.js";

const app = new Hono();
const hasFrontend = existsSync("./public/index.html");

app.use("*", logger());
app.onError((err, c) => c.json({ error: err.message || "Internal error" }, 500));

app.route("/health", health);
app.use("/api/*", authMiddleware);
app.route("/api/agents", agents);
app.route("/api/notion", notion);
app.route("/api/comfyui", comfyui);

if (hasFrontend) {
  app.use("/assets/*", serveStatic({ root: "./public" }));
  app.use("/favicon.ico", serveStatic({ root: "./public" }));
  app.get("*", serveStatic({ root: "./public", path: "index.html" }));
} else {
  app.get("/", (c) => c.json({ name: "mascarade-api", version: "0.1.0" }));
}

app.notFound((c) => c.json({ error: "Not found" }, 404));

const port = parseInt(process.env.API_PORT || "3000", 10);

console.log(`Mascarade API listening on port ${port}`);
serve({ fetch: app.fetch, port });

export { app };

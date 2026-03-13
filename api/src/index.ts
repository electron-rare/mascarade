import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { Hono } from "hono";
import { logger } from "hono/logger";
import { existsSync } from "node:fs";
import { authMiddleware } from "./middleware/auth.js";
import { corsMiddleware } from "./middleware/cors.js";
import { rateLimitMiddleware } from "./middleware/rate-limit.js";
import { securityHeaders } from "./middleware/security.js";
import { health } from "./routes/health.js";
import { version } from "./routes/version.js";
import { agents } from "./routes/agents.js";
import { cluster } from "./routes/cluster.js";
import { knowledgeBase } from "./routes/knowledgeBase.js";
import { qdrantKnowledge } from "./routes/qdrantKnowledge.js";
import { cad } from "./routes/cad.js";
import { comfyui } from "./routes/comfyui.js";
import { ops } from "./routes/ops.js";
import { industrial } from "./routes/industrial.js";
import { industrialMcp } from "./routes/mcpIndustrial.js";
import { killlife } from "./routes/killlife.js";
import { settings } from "./routes/settings.js";

const app = new Hono();
const hasFrontend = existsSync("./public/index.html");

app.use("*", corsMiddleware);
app.use("*", securityHeaders);
app.use("*", logger());
app.onError((err, c) => {
  console.error("Internal error:", err);
  return c.json({ error: "Internal server error" }, 500);
});

app.route("/health", health);
app.route("/v1/version", version);
// Auth first — reject unauthenticated before consuming rate-limit quota
app.use("/v1/api/*", authMiddleware);
app.use("/v1/api/*", rateLimitMiddleware);
app.route("/v1/api/agents", agents);
app.route("/v1/api/cluster", cluster);
app.route("/v1/api/knowledge-base", knowledgeBase);
app.route("/v1/api/qdrant-knowledge", qdrantKnowledge);
app.route("/v1/api/cad", cad);
app.route("/v1/api/comfyui", comfyui);
app.route("/v1/api/ops", ops);
app.route("/v1/api/industrial", industrial);
app.route("/v1/api/mcp/industrial", industrialMcp);
app.route("/v1/api/killlife", killlife);
app.route("/v1/api/settings", settings);

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

import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { Hono } from "hono";
import { logger } from "hono/logger";
import { existsSync } from "node:fs";
import { authMiddleware } from "./middleware/auth.js";
import { corsMiddleware } from "./middleware/cors.js";
import { rateLimitMiddleware } from "./middleware/rate-limit.js";
import { securityHeaders } from "./middleware/security.js";
import { auth } from "./routes/auth.js";
import { health } from "./routes/health.js";
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
import { analytics } from "./routes/analytics.js";
import { users } from "./routes/users.js";
import { p2p } from "./routes/p2p.js";
import { finetune } from "./routes/finetune.js";

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
app.use("/api/auth/*", rateLimitMiddleware);
app.route("/api/auth", auth);
// Auth first — reject unauthenticated before consuming rate-limit quota
app.use("/api/*", authMiddleware);
app.use("/api/*", rateLimitMiddleware);
app.route("/api/agents", agents);
app.route("/api/cluster", cluster);
app.route("/api/knowledge-base", knowledgeBase);
app.route("/api/qdrant-knowledge", qdrantKnowledge);
app.route("/api/cad", cad);
app.route("/api/comfyui", comfyui);
app.route("/api/ops", ops);
app.route("/api/industrial", industrial);
app.route("/api/mcp/industrial", industrialMcp);
app.route("/api/killlife", killlife);
app.route("/api/settings", settings);
app.route("/api/analytics", analytics);
app.route("/api/users", users);
app.route("/api/p2p", p2p);
app.route("/api/finetune", finetune);

// Node Engine UI route
app.get("/node-engine", serveStatic({ root: "./public", path: "node-engine.html" }));
app.use("/node-engine-bundle.js*", serveStatic({ root: "./public" }));

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

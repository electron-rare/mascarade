import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { logger } from "hono/logger";
import { authMiddleware } from "./middleware/auth.js";
import { health } from "./routes/health.js";
import { agents } from "./routes/agents.js";
import { notion } from "./routes/notion.js";
import { comfyui } from "./routes/comfyui.js";

const app = new Hono();

app.use("*", logger());
app.onError((err, c) => c.json({ error: err.message || "Internal error" }, 500));
app.notFound((c) => c.json({ error: "Not found" }, 404));

app.route("/health", health);
app.use("/api/*", authMiddleware);
app.route("/api/agents", agents);
app.route("/api/notion", notion);
app.route("/api/comfyui", comfyui);

app.get("/", (c) => c.json({ name: "mascarade-api", version: "0.1.0" }));

const port = parseInt(process.env.API_PORT || "3000", 10);

console.log(`Mascarade API listening on port ${port}`);
serve({ fetch: app.fetch, port });

export { app };

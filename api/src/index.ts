import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { logger } from "hono/logger";
import { health } from "./routes/health.js";
import { agents } from "./routes/agents.js";

const app = new Hono();

app.use("*", logger());

app.route("/health", health);
app.route("/api/agents", agents);

app.get("/", (c) => c.json({ name: "mascarade-api", version: "0.1.0" }));

const port = parseInt(process.env.API_PORT || "3000", 10);

console.log(`Mascarade API listening on port ${port}`);
serve({ fetch: app.fetch, port });

export { app };

import { Hono, type Context } from "hono";
import { emitStructuredLog } from "../lib/otel.js";

const pipeline = new Hono();

/**
 * POST /run - Trigger pipeline execution
 * TODO: Implementation in subtask-4-2
 */
pipeline.post("/run", async (c: Context) => {
  emitStructuredLog({
    severity: "info",
    source: "api",
    service: "pipeline",
    message: "Pipeline run endpoint called (not yet implemented)",
  });
  return c.json({ status: "not_implemented" }, 501);
});

/**
 * GET /status - Check pipeline state
 * TODO: Implementation in subtask-4-3
 */
pipeline.get("/status", async (c: Context) => {
  return c.json({ status: "not_implemented" }, 501);
});

/**
 * GET /models - List fine-tuned models from registry
 * TODO: Implementation in subtask-4-4
 */
pipeline.get("/models", async (c: Context) => {
  return c.json({ status: "not_implemented" }, 501);
});

export { pipeline };

import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";
import {
  CliAgentRunRequestSchema,
  type CliAgentRunRequest,
} from "../validation/index.js";

const cliAgents = new Hono();

cliAgents.get("/status", async (c) => {
  try {
    return c.json(await coreClient.cliAgentsStatus());
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cliAgents.post("/run", async (c) => {
  try {
    let raw: unknown;
    try {
      raw = await c.req.json();
    } catch {
      return c.json({ error: "Validation failed", details: [{ message: "Request body is not valid JSON" }] }, 400);
    }
    const parsed = CliAgentRunRequestSchema.safeParse(raw);
    if (!parsed.success) {
      return c.json({
        error: "Validation failed",
        details: parsed.error.issues.map((issue: { path: (string | number)[]; message: string; code: string }) => ({
          path: issue.path.join("."),
          message: issue.message,
          code: issue.code,
        })),
      }, 400);
    }

    const body = parsed.data as CliAgentRunRequest;
    return c.json(await coreClient.runCliAgent(body));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { cliAgents };

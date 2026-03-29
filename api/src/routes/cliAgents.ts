import { Hono } from "hono";
import { CoreApiError, coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";
import { validate } from "../validation/index.js";
import { CliAgentRunRequestSchema } from "../validation/schemas.js";

const cliAgents = new Hono();

cliAgents.get("/status", async (c) => {
  try {
    const result = await coreClient.cliAgentsStatus();
    return c.json(result);
  } catch (error) {
    if (error instanceof CoreApiError) {
      const { status, body } = handleCoreError(error);
      return c.json(body, status);
    }
    return c.json({ error: "Internal server error" }, 500);
  }
});

cliAgents.post("/run", validate(CliAgentRunRequestSchema), async (c) => {
  try {
    const body = c.get("validated" as never);
    const result = await coreClient.runCliAgent(body as any);
    return c.json(result);
  } catch (error) {
    if (error instanceof CoreApiError) {
      const { status, body } = handleCoreError(error);
      return c.json(body, status);
    }
    return c.json({ error: "Internal server error" }, 500);
  }
});

export { cliAgents };

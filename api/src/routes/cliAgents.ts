import { Hono } from "hono";
import { CoreApiError, coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const cliAgents = new Hono();

cliAgents.post("/run", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.runCliAgent(body);
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

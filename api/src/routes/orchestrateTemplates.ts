import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const orchestrateTemplates = new Hono();

orchestrateTemplates.get("/", async (c) => {
  try {
    const result = await coreClient.listTemplates();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

orchestrateTemplates.get("/:id", async (c) => {
  try {
    const id = c.req.param("id");
    const result = await coreClient.getTemplate(id);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

orchestrateTemplates.post("/:id/deploy", async (c) => {
  try {
    const id = c.req.param("id");
    const body = await c.req.json();
    const result = await coreClient.deployTemplate(id, body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { orchestrateTemplates };

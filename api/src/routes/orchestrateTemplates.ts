import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";
import { validate } from "../validation/index.js";
import {
  TemplateDeployRequestSchema,
  WorkflowTemplateCreateRequestSchema,
  WorkflowTemplateUpdateRequestSchema,
} from "../validation/schemas.js";

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
    if (!id) {
      return c.json({ error: "Missing template id" }, 400);
    }
    const result = await coreClient.getTemplate(id);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

orchestrateTemplates.post(
  "/",
  validate(WorkflowTemplateCreateRequestSchema),
  async (c) => {
    try {
      const body = c.get("validated" as never);
      const result = await coreClient.createTemplate(body as any);
      return c.json(result, 201);
    } catch (error) {
      const { status, body } = handleCoreError(error);
      return c.json(body, status);
    }
  },
);

orchestrateTemplates.put(
  "/:id",
  validate(WorkflowTemplateUpdateRequestSchema),
  async (c) => {
    try {
      const id = c.req.param("id");
      if (!id) {
        return c.json({ error: "Missing template id" }, 400);
      }
      const body = c.get("validated" as never);
      const result = await coreClient.updateTemplate(id, body as any);
      return c.json(result);
    } catch (error) {
      const { status, body } = handleCoreError(error);
      return c.json(body, status);
    }
  },
);

orchestrateTemplates.delete("/:id", async (c) => {
  try {
    const id = c.req.param("id");
    if (!id) {
      return c.json({ error: "Missing template id" }, 400);
    }
    const result = await coreClient.deleteTemplate(id);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

orchestrateTemplates.post("/:id/deploy", validate(TemplateDeployRequestSchema), async (c) => {
  try {
    const id = c.req.param("id");
    if (!id) {
      return c.json({ error: "Missing template id" }, 400);
    }
    const body = c.get("validated" as never);
    const result = await coreClient.deployTemplate(id, body as any);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { orchestrateTemplates };

import { Hono } from "hono";
import { z } from "zod";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const industrial = new Hono();

// --- P0-2: Validate tool arguments to prevent injection and oversized payloads ---
const MAX_TOOL_ARGS_SIZE = 64 * 1024; // 64 KB max serialized size

const ToolCallBodySchema = z.object({
  arguments: z
    .record(z.string(), z.unknown())
    .optional()
    .refine(
      (args) => {
        if (!args) return true;
        return JSON.stringify(args).length <= MAX_TOOL_ARGS_SIZE;
      },
      { message: `Tool arguments exceed max size (${MAX_TOOL_ARGS_SIZE} bytes)` },
    ),
  run_id: z.string().max(256).optional(),
}).strict();

industrial.get("/servers", async (c) => {
  try {
    const payload = await coreClient.industrialMcpServers();
    return c.json(payload);
  } catch (error) {
    const handled = handleCoreError(error);
    return c.json(handled.body, handled.status);
  }
});

industrial.get("/platform", async (c) => {
  try {
    const payload = await coreClient.industrialMcpPlatform();
    return c.json(payload);
  } catch (error) {
    const handled = handleCoreError(error);
    return c.json(handled.body, handled.status);
  }
});

industrial.get("/:serverKey/runtime", async (c) => {
  try {
    const payload = await coreClient.industrialMcpRuntime(c.req.param("serverKey"));
    return c.json(payload);
  } catch (error) {
    const handled = handleCoreError(error);
    return c.json(handled.body, handled.status);
  }
});

industrial.get("/:serverKey/resource", async (c) => {
  try {
    const uri = c.req.query("uri");
    if (!uri) {
      return c.json({ error: "Missing required query parameter 'uri'" }, 400);
    }
    const payload = await coreClient.industrialMcpResource(c.req.param("serverKey"), uri);
    return c.json(payload);
  } catch (error) {
    const handled = handleCoreError(error);
    return c.json(handled.body, handled.status);
  }
});

industrial.post("/:serverKey/tools/:toolName", async (c) => {
  try {
    const rawBody = await c.req.json().catch(() => ({}));
    const parsed = ToolCallBodySchema.safeParse(rawBody);
    if (!parsed.success) {
      return c.json(
        { error: "Invalid tool call body", details: parsed.error.issues },
        400,
      );
    }
    const body = parsed.data;
    const payload = await coreClient.industrialMcpTool(
      c.req.param("serverKey"),
      c.req.param("toolName"),
      {
        arguments: body.arguments,
        run_id: body.run_id,
      },
    );
    return c.json(payload);
  } catch (error) {
    const handled = handleCoreError(error);
    return c.json(handled.body, handled.status);
  }
});

export { industrial };

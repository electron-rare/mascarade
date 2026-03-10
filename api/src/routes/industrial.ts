import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const industrial = new Hono();

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
    const body = (await c.req.json().catch(() => ({}))) as {
      arguments?: Record<string, unknown>;
      run_id?: string;
    };
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

import { Hono } from "hono";
import { coreClient } from "../client/core.js";

const health = new Hono();

health.get("/", async (c) => {
  try {
    const coreHealth = await coreClient.health();
    return c.json({
      status: "ok",
      core: coreHealth,
    });
  } catch {
    return c.json({ status: "degraded", core: "unreachable" }, 503);
  }
});

export { health };

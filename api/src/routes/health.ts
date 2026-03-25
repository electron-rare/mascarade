import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { allowPublicApi, isAuthConfigured } from "../middleware/auth.js";

const health = new Hono();

health.get("/", async (c) => {
  const auth_required = isAuthConfigured() && !allowPublicApi();
  try {
    const coreHealth = await coreClient.health();
    return c.json({ status: "ok", auth_required, core: coreHealth });
  } catch {
    return c.json({ status: "degraded", auth_required, core: "unreachable" }, 503);
  }
});

export { health };

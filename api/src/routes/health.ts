import { Hono } from "hono";
import { coreClient } from "../client/core.js";

const health = new Hono();

function isAuthRequired(): boolean {
  return (process.env.MASCARADE_API_KEY || "")
    .split(",")
    .some((k) => k.trim().length >= 16);
}

health.get("/", async (c) => {
  const auth_required = isAuthRequired();
  try {
    const coreHealth = await coreClient.health();
    return c.json({ status: "ok", auth_required, core: coreHealth });
  } catch {
    return c.json({ status: "degraded", auth_required, core: "unreachable" }, 503);
  }
});

export { health };

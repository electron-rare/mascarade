import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const cluster = new Hono();

cluster.get("/identity", async (c) => {
  try {
    const result = await coreClient.clusterIdentity();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cluster.get("/peers", async (c) => {
  try {
    const result = await coreClient.clusterPeers();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cluster.post("/forward/send", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.clusterForwardSend(body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { cluster };

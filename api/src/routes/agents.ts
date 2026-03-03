import { Hono } from "hono";
import { CoreApiError, coreClient } from "../client/core.js";

const agents = new Hono();

function handleCoreError(error: unknown) {
  if (error instanceof CoreApiError) {
    const status = error.status >= 400 && error.status < 500 ? (400 as const) : (502 as const);
    return {
      status,
      body: { error: error.message, core_status: error.status },
    };
  }
  return {
    status: 502 as const,
    body: { error: "Core service unreachable" },
  };
}

/** Lister tous les agents */
agents.get("/", async (c) => {
  try {
    const result = await coreClient.listAgents();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Créer un agent */
agents.post("/", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.createAgent(body);
    return c.json(result, 201);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Exécuter un agent */
agents.post("/:name/run", async (c) => {
  try {
    const name = c.req.param("name");
    const { messages } = await c.req.json();
    const result = await coreClient.runAgent(name, messages);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Envoyer un prompt avec routage */
agents.post("/send", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.send(body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Orchestrer plusieurs agents */
agents.post("/orchestrate", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.orchestrate(body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Lister les providers disponibles */
agents.get("/providers", async (c) => {
  try {
    const result = await coreClient.listProviders();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { agents };

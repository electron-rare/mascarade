import { Hono } from "hono";
import { coreClient } from "../client/core.js";

const agents = new Hono();

/** Lister tous les agents */
agents.get("/", async (c) => {
  const result = await coreClient.listAgents();
  return c.json(result);
});

/** Créer un agent */
agents.post("/", async (c) => {
  const body = await c.req.json();
  const result = await coreClient.createAgent(body);
  return c.json(result, 201);
});

/** Exécuter un agent */
agents.post("/:name/run", async (c) => {
  const name = c.req.param("name");
  const { messages } = await c.req.json();
  const result = await coreClient.runAgent(name, messages);
  return c.json(result);
});

/** Envoyer un prompt avec routage */
agents.post("/send", async (c) => {
  const body = await c.req.json();
  const result = await coreClient.send(body);
  return c.json(result);
});

/** Orchestrer plusieurs agents */
agents.post("/orchestrate", async (c) => {
  const body = await c.req.json();
  const result = await coreClient.orchestrate(body);
  return c.json(result);
});

/** Lister les providers disponibles */
agents.get("/providers", async (c) => {
  const result = await coreClient.listProviders();
  return c.json(result);
});

export { agents };

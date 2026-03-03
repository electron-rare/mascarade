import { Hono } from "hono";
import { CoreApiError, coreClient } from "../client/core.js";

const notion = new Hono();

function handleCoreError(error: unknown) {
  if (error instanceof CoreApiError) {
    const status = error.status >= 400 && error.status < 500 ? (400 as const) : (502 as const);
    return { status, body: { error: error.message, core_status: error.status } };
  }
  return { status: 502 as const, body: { error: "Core service unreachable" } };
}

/** Rechercher dans la KB Notion */
notion.get("/search", async (c) => {
  try {
    const q = c.req.query("q") || "";
    const result = await coreClient.notionSearch(q);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Lire le contenu d'une page */
notion.get("/pages/:pageId", async (c) => {
  try {
    const result = await coreClient.notionReadPage(c.req.param("pageId"));
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Ajouter du contenu à une page */
notion.post("/pages/:pageId/append", async (c) => {
  try {
    const { content } = await c.req.json();
    const result = await coreClient.notionAppend(c.req.param("pageId"), content);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Créer une nouvelle page */
notion.post("/pages", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.notionCreatePage(body);
    return c.json(result, 201);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { notion };

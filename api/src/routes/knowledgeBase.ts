import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const knowledgeBase = new Hono();

/** Rechercher dans la knowledge base */
knowledgeBase.get("/search", async (c) => {
  try {
    const q = (c.req.query("q") || "").slice(0, 1000);
    const result = await coreClient.knowledgeBaseSearch(q);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Lire le contenu d'une page */
knowledgeBase.get("/pages/:pageId", async (c) => {
  try {
    const pageId = c.req.param("pageId");
    if (!pageId || pageId.length > 512) {
      return c.json({ error: "Invalid page ID" }, 400);
    }
    const result = await coreClient.knowledgeBaseReadPage(pageId);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Ajouter du contenu a une page */
knowledgeBase.post("/pages/:pageId/append", async (c) => {
  try {
    const pageId = c.req.param("pageId");
    if (!pageId || pageId.length > 512) {
      return c.json({ error: "Invalid page ID" }, 400);
    }
    const { content } = await c.req.json();
    const result = await coreClient.knowledgeBaseAppend(pageId, content);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Creer une nouvelle page */
knowledgeBase.post("/pages", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.knowledgeBaseCreatePage(body);
    return c.json(result, 201);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { knowledgeBase };

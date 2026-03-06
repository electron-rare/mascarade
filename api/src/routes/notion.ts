import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const notion = new Hono();
const NOTION_ID_RE = /^[a-f0-9-]+$/i;

/** Rechercher dans la KB Notion */
notion.get("/search", async (c) => {
  try {
    const q = (c.req.query("q") || "").slice(0, 1000);
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
    const pageId = c.req.param("pageId");
    if (!pageId || !NOTION_ID_RE.test(pageId)) {
      return c.json({ error: "Invalid page ID" }, 400);
    }
    const result = await coreClient.notionReadPage(pageId);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Ajouter du contenu a une page */
notion.post("/pages/:pageId/append", async (c) => {
  try {
    const pageId = c.req.param("pageId");
    if (!pageId || !NOTION_ID_RE.test(pageId)) {
      return c.json({ error: "Invalid page ID" }, 400);
    }
    const { content } = await c.req.json();
    const result = await coreClient.notionAppend(pageId, content);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Creer une nouvelle page */
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

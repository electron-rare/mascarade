import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";
import {
  KnowledgeBaseSearchSchema,
  type KnowledgeBaseSearch,
} from "../validation/index.js";

const knowledgeBase = new Hono();

/** Rechercher dans la knowledge base */
knowledgeBase.get("/search", async (c) => {
  try {
    // Pre-process query params: coerce limit to number for Zod validation
    const rawQuery: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(c.req.query())) {
      rawQuery[key] = value;
    }
    if (typeof rawQuery.limit === "string") {
      const parsed = Number.parseInt(rawQuery.limit, 10);
      rawQuery.limit = Number.isFinite(parsed) ? parsed : rawQuery.limit;
    }

    const parsed = KnowledgeBaseSearchSchema.safeParse(rawQuery);
    if (!parsed.success) {
      return c.json(
        {
          error: "Query validation failed",
          details: parsed.error.issues.map((issue: { path: (string | number)[]; message: string; code: string }) => ({
            path: issue.path.join("."),
            message: issue.message,
            code: issue.code,
          })),
        },
        400,
      );
    }

    const validated = parsed.data as KnowledgeBaseSearch;
    const federationScope =
      validated.federation_scope
        ?.split(",")
        .map((value: string) => value.trim())
        .filter(Boolean) || undefined;
    const result = await coreClient.knowledgeBaseSearch(validated.q, {
      limit: validated.limit,
      projectId: validated.project_id,
      federationScope,
      knowledgeScope: validated.knowledge_scope,
    });
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

import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const qdrantKnowledge = new Hono();

/** Health check for Qdrant */
qdrantKnowledge.get("/health", async (c) => {
  try {
    const result = await coreClient.qdrantHealth();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** List all Qdrant collections */
qdrantKnowledge.get("/collections", async (c) => {
  try {
    const result = await coreClient.qdrantListCollections();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Get collection details */
qdrantKnowledge.get("/collections/:collectionName", async (c) => {
  try {
    const collectionName = c.req.param("collectionName");
    if (!collectionName || collectionName.length > 256) {
      return c.json({ error: "Invalid collection name" }, 400);
    }
    const result = await coreClient.qdrantGetCollection(collectionName);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Create a new collection */
qdrantKnowledge.put("/collections/:collectionName", async (c) => {
  try {
    const collectionName = c.req.param("collectionName");
    if (!collectionName || collectionName.length > 256) {
      return c.json({ error: "Invalid collection name" }, 400);
    }
    const body = await c.req.json();
    const result = await coreClient.qdrantCreateCollection(collectionName, body);
    return c.json(result, 201);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Delete a collection */
qdrantKnowledge.delete("/collections/:collectionName", async (c) => {
  try {
    const collectionName = c.req.param("collectionName");
    if (!collectionName || collectionName.length > 256) {
      return c.json({ error: "Invalid collection name" }, 400);
    }
    const result = await coreClient.qdrantDeleteCollection(collectionName);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Upsert points into a collection */
qdrantKnowledge.post("/collections/:collectionName/points", async (c) => {
  try {
    const collectionName = c.req.param("collectionName");
    if (!collectionName || collectionName.length > 256) {
      return c.json({ error: "Invalid collection name" }, 400);
    }
    const body = await c.req.json();
    const result = await coreClient.qdrantUpsertPoints(collectionName, body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Search for similar vectors */
qdrantKnowledge.post("/collections/:collectionName/search", async (c) => {
  try {
    const collectionName = c.req.param("collectionName");
    if (!collectionName || collectionName.length > 256) {
      return c.json({ error: "Invalid collection name" }, 400);
    }
    const body = await c.req.json();
    const result = await coreClient.qdrantSearch(collectionName, body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Get recommendations based on positive/negative examples */
qdrantKnowledge.post("/collections/:collectionName/recommend", async (c) => {
  try {
    const collectionName = c.req.param("collectionName");
    if (!collectionName || collectionName.length > 256) {
      return c.json({ error: "Invalid collection name" }, 400);
    }
    const body = await c.req.json();
    const result = await coreClient.qdrantRecommend(collectionName, body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { qdrantKnowledge };

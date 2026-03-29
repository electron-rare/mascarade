import { test, expect } from "@playwright/test";

const VALID_TOKEN = "mock-valid-token-32chars-test";

/**
 * Tests E2E — Pipeline RAG
 * Couvre query, ingest et stats du pipeline RAG (bge-m3 → Qdrant).
 */
test.describe("RAG /v1/api/rag", () => {
  test.describe("GET /v1/api/rag/stats", () => {
    test("retourne 401 sans token", async ({ request }) => {
      const res = await request.get("/v1/api/rag/stats");
      expect([401, 503]).toContain(res.status());
    });

    test("retourne les statistiques du pipeline avec token valide", async ({ request }) => {
      const res = await request.get("/v1/api/rag/stats", {
        headers: { Authorization: `Bearer ${VALID_TOKEN}` },
      });
      expect(res.status()).toBe(200);
      const body = await res.json();
      expect(body).toMatchObject({
        collection: expect.any(String),
        documents: expect.any(Number),
        embedding_model: expect.any(String),
        status: expect.stringMatching(/^(ok|degraded)$/),
      });
    });
  });

  test.describe("POST /v1/api/rag/query", () => {
    test("retourne 401 sans token", async ({ request }) => {
      const res = await request.post("/v1/api/rag/query", {
        data: { query: "test" },
      });
      expect([401, 503]).toContain(res.status());
    });

    test("retourne 400 si query manquant", async ({ request }) => {
      const res = await request.post("/v1/api/rag/query", {
        headers: { Authorization: `Bearer ${VALID_TOKEN}` },
        data: {},
      });
      expect(res.status()).toBe(400);
    });

    test("retourne des résultats pertinents pour une query valide", async ({ request }) => {
      const res = await request.post("/v1/api/rag/query", {
        headers: { Authorization: `Bearer ${VALID_TOKEN}` },
        data: { query: "pipeline RAG embeddings" },
      });
      expect(res.status()).toBe(200);
      const body = await res.json();
      expect(body).toMatchObject({
        query: "pipeline RAG embeddings",
        results: expect.any(Array),
        tokens: expect.any(Number),
      });
      expect(body.results.length).toBeGreaterThan(0);
      expect(body.results[0]).toMatchObject({
        content: expect.any(String),
        score: expect.any(Number),
        source: expect.any(String),
      });
    });

    test("le score du premier résultat est supérieur à 0.5", async ({ request }) => {
      const res = await request.post("/v1/api/rag/query", {
        headers: { Authorization: `Bearer ${VALID_TOKEN}` },
        data: { query: "Qdrant vecteurs" },
      });
      expect(res.status()).toBe(200);
      const body = await res.json();
      expect(body.results[0].score).toBeGreaterThan(0.5);
    });
  });

  test.describe("POST /v1/api/rag/ingest", () => {
    test("retourne 401 sans token", async ({ request }) => {
      const res = await request.post("/v1/api/rag/ingest", {
        data: { text: "doc test" },
      });
      expect([401, 503]).toContain(res.status());
    });

    test("retourne 400 si text manquant", async ({ request }) => {
      const res = await request.post("/v1/api/rag/ingest", {
        headers: { Authorization: `Bearer ${VALID_TOKEN}` },
        data: {},
      });
      expect(res.status()).toBe(400);
    });

    test("indexe un document et retourne un id", async ({ request }) => {
      const res = await request.post("/v1/api/rag/ingest", {
        headers: { Authorization: `Bearer ${VALID_TOKEN}` },
        data: {
          text: "Le LM2596 est un régulateur de tension step-down.",
          source: "datasheets/lm2596",
          metadata: { type: "datasheet" },
        },
      });
      expect(res.status()).toBe(200);
      const body = await res.json();
      expect(body).toMatchObject({
        id: expect.any(String),
        chunks: expect.any(Number),
        status: "indexed",
      });
    });
  });
});

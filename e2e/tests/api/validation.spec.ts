import { test, expect } from "@playwright/test";

/**
 * Tests E2E — Validation des limites de payload
 * Vérifie que la gateway rejette les requêtes dépassant les limites définies.
 */

const VALID_TOKEN = "mock-valid-token-32chars-test";
const authHeader = { Authorization: `Bearer ${VALID_TOKEN}` };

test.describe("Validation — /api/v1/chat/completions", () => {
  test("accepte un payload valide (< 100 messages)", async ({ request }) => {
    const res = await request.post("/api/v1/chat/completions", {
      headers: authHeader,
      data: {
        messages: [{ role: "user", content: "Bonjour !" }],
        max_tokens: 512,
      },
    });
    expect(res.status()).toBe(200);
  });

  test("rejette un tableau de messages dépassant 100 (oversized array)", async ({ request }) => {
    const messages = Array.from({ length: 101 }, (_, i) => ({
      role: i % 2 === 0 ? "user" : "assistant",
      content: `Message ${i}`,
    }));

    const res = await request.post("/api/v1/chat/completions", {
      headers: authHeader,
      data: { messages },
    });
    expect(res.status()).toBe(400);
  });

  test("rejette un message dont le contenu dépasse 50 000 caractères", async ({ request }) => {
    const res = await request.post("/api/v1/chat/completions", {
      headers: authHeader,
      data: {
        messages: [{ role: "user", content: "A".repeat(50_001) }],
      },
    });
    expect(res.status()).toBe(400);
  });

  test("accepte exactement 100 messages (limite autorisée)", async ({ request }) => {
    const messages = Array.from({ length: 100 }, (_, i) => ({
      role: i % 2 === 0 ? "user" : "assistant",
      content: `msg ${i}`,
    }));

    const res = await request.post("/api/v1/chat/completions", {
      headers: authHeader,
      data: { messages },
    });
    expect(res.status()).toBe(200);
  });
});

test.describe("Validation — /api/agents/run", () => {
  test("accepte un prompt valide", async ({ request }) => {
    const res = await request.post("/api/agents/run", {
      headers: authHeader,
      data: {
        prompt: "Analyse ce code Python.",
        agent: "coder",
      },
    });
    expect(res.status()).toBe(200);
  });

  test("rejette un prompt dépassant 50 000 caractères", async ({ request }) => {
    const res = await request.post("/api/agents/run", {
      headers: authHeader,
      data: {
        prompt: "X".repeat(50_001),
        agent: "coder",
      },
    });
    expect(res.status()).toBe(400);
  });
});

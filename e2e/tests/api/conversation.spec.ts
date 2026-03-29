import { test, expect } from "@playwright/test";

const VALID_TOKEN = "mock-valid-token-32chars-test";

/**
 * Tests E2E — Conversation (POST /api/v1/chat/completions)
 * Couvre le flux de chat : requête valide, gestion d'erreurs, limites.
 */
test.describe("Conversation /api/v1/chat/completions", () => {
  test("retourne 401 sans token", async ({ request }) => {
    const res = await request.post("/api/v1/chat/completions", {
      data: {
        model: "mistral:7b",
        messages: [{ role: "user", content: "Bonjour" }],
      },
    });
    expect([401, 503]).toContain(res.status());
  });

  test("retourne une réponse de l'assistant pour un message valide", async ({ request }) => {
    const res = await request.post("/api/v1/chat/completions", {
      headers: { Authorization: `Bearer ${VALID_TOKEN}` },
      data: {
        model: "mistral:7b",
        messages: [{ role: "user", content: "Bonjour, comment tu vas ?" }],
      },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({
      id: expect.any(String),
      choices: expect.any(Array),
      usage: {
        input_tokens: expect.any(Number),
        output_tokens: expect.any(Number),
        total_tokens: expect.any(Number),
      },
    });
    expect(body.choices.length).toBeGreaterThan(0);
    expect(body.choices[0].message.role).toBe("assistant");
    expect(body.choices[0].message.content).toBeTruthy();
    expect(body.choices[0].finish_reason).toBe("stop");
  });

  test("support du mode multi-tour (historique inclus)", async ({ request }) => {
    const res = await request.post("/api/v1/chat/completions", {
      headers: { Authorization: `Bearer ${VALID_TOKEN}` },
      data: {
        model: "mistral:7b",
        messages: [
          { role: "user", content: "Explique le RAG." },
          { role: "assistant", content: "Le RAG combine recherche et génération." },
          { role: "user", content: "Donne-moi un exemple avec Qdrant." },
        ],
      },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.choices[0].message.content).toBeTruthy();
  });

  test("retourne 400 si le nombre de messages dépasse 100", async ({ request }) => {
    const messages = Array.from({ length: 101 }, (_, i) => ({
      role: i % 2 === 0 ? "user" : "assistant",
      content: `Message ${i}`,
    }));
    const res = await request.post("/api/v1/chat/completions", {
      headers: { Authorization: `Bearer ${VALID_TOKEN}` },
      data: { model: "mistral:7b", messages },
    });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.error).toMatch(/max 100/i);
  });

  test("retourne 400 si le contenu d'un message dépasse la limite", async ({ request }) => {
    const res = await request.post("/api/v1/chat/completions", {
      headers: { Authorization: `Bearer ${VALID_TOKEN}` },
      data: {
        model: "mistral:7b",
        messages: [{ role: "user", content: "x".repeat(51_000) }],
      },
    });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.error).toMatch(/limit|exceeds/i);
  });

  test("les tokens utilisés sont cohérents (total = input + output)", async ({ request }) => {
    const res = await request.post("/api/v1/chat/completions", {
      headers: { Authorization: `Bearer ${VALID_TOKEN}` },
      data: {
        model: "mistral:7b",
        messages: [{ role: "user", content: "Résume l'architecture mascarade." }],
      },
    });
    expect(res.status()).toBe(200);
    const { usage } = await res.json();
    expect(usage.total_tokens).toBe(usage.input_tokens + usage.output_tokens);
  });
});

/**
 * Mock API server pour les tests E2E Playwright.
 * Simule le behaviour de sécurité de la gateway Mascarade:
 *  - Fail-closed (503) quand aucune auth configurée → token absent
 *  - 401 pour un token invalide
 *  - 200 pour le token valide
 *  - /health toujours accessible
 */
import http from "http";

const PORT = 3111;
export const VALID_TOKEN = "mock-valid-token-32chars-test";

function getAuth(req) {
  const authHeader = req.headers["authorization"] || "";
  const cookieHeader = req.headers["cookie"] || "";

  const bearerMatch = authHeader.match(/^Bearer (.+)$/);
  if (bearerMatch) return bearerMatch[1];

  const cookieMatch = cookieHeader.match(/mascarade_key=([^;]+)/);
  if (cookieMatch) return decodeURIComponent(cookieMatch[1]);

  return null;
}

function authGuard(req) {
  const token = getAuth(req);
  if (!token) return { status: 503, body: { error: "Authentification non configuree" } };
  if (token !== VALID_TOKEN) return { status: 401, body: { error: "Token invalide ou expiré" } };
  return null;
}

const routes = {
  "GET /health": () => ({
    status: 200,
    body: {
      status: "ok",
      auth_required: true,
      core: {
        status: "ok",
        providers: ["openai", "ollama"],
        agents: 5,
      },
    },
  }),

  "GET /api/agents": (req) => {
    const guard = authGuard(req);
    if (guard) return guard;
    return {
      status: 200,
      body: [
        { name: "agent-zero", description: "Lead agent généraliste", builtin: true, strategy: "best" },
        { name: "coder", description: "Assistant code Python / TypeScript", builtin: false, strategy: "fastest" },
        { name: "analyst", description: "Analyse de données et synthèse", builtin: false, strategy: "cheapest" },
      ],
    };
  },

  "GET /api/agents/providers": (req) => {
    const guard = authGuard(req);
    if (guard) return guard;
    return { status: 200, body: { providers: ["openai", "ollama"] } };
  },

  "GET /api/ops/monitor": (req) => {
    const guard = authGuard(req);
    if (guard) return guard;
    return {
      status: 200,
      body: {
        ai: {
          ollama: { ok: true, models: 2, model_names: ["llama3.2", "mistral:7b"] },
        },
        services: {
          core: { ok: true },
          db: { ok: false },
        },
      },
    };
  },

  "GET /api/settings": (req) => {
    const guard = authGuard(req);
    if (guard) return guard;
    return { status: 200, body: { providers: [], runtime_secrets: [] } };
  },

  "GET /api/version": (req) => {
    const guard = authGuard(req);
    if (guard) return guard;
    return { status: 200, body: { version: "0.1.0", commit: "e2e-mock" } };
  },

  "POST /api/v1/chat/completions": (req, body) => {
    const guard = authGuard(req);
    if (guard) return guard;

    // Validation: nombre de messages
    if (body?.messages && body.messages.length > 100) {
      return { status: 400, body: { error: "Too many messages (max 100)" } };
    }
    // Validation: contenu trop long
    const tooLong = (body?.messages || []).some((m) => m.content?.length > 50_000);
    if (tooLong) {
      return { status: 400, body: { error: "Message content exceeds limit" } };
    }

    return {
      status: 200,
      body: {
        id: "mock-chat-001",
        choices: [{ message: { role: "assistant", content: "Bonjour ! Comment puis-je vous aider ?" }, finish_reason: "stop" }],
        usage: { input_tokens: 12, output_tokens: 9, total_tokens: 21 },
      },
    };
  },

  "POST /api/agents/run": (req, body) => {
    const guard = authGuard(req);
    if (guard) return guard;
    if (body?.prompt && body.prompt.length > 50_000) {
      return { status: 400, body: { error: "Prompt exceeds maximum length" } };
    }
    return {
      status: 200,
      body: { response: "Tâche traitée par l'agent.", tokens: 50, cost: 0.001 },
    };
  },

  "POST /v1/api/rag/query": (req, body) => {
    const guard = authGuard(req);
    if (guard) return guard;
    if (!body?.query) {
      return { status: 400, body: { error: "query est requis" } };
    }
    return {
      status: 200,
      body: {
        query: body.query,
        results: [
          { content: "Le pipeline RAG utilise bge-m3 pour les embeddings.", score: 0.92, source: "docs/ARCHITECTURE.md" },
          { content: "Qdrant est utilisé comme base vectorielle.", score: 0.87, source: "core/mascarade/rag/pipeline.py" },
        ],
        tokens: 42,
      },
    };
  },

  "POST /v1/api/rag/ingest": (req, body) => {
    const guard = authGuard(req);
    if (guard) return guard;
    if (!body?.text) {
      return { status: 400, body: { error: "text est requis" } };
    }
    return {
      status: 200,
      body: { id: "doc-mock-001", chunks: 3, status: "indexed" },
    };
  },

  "GET /v1/api/rag/stats": (req) => {
    const guard = authGuard(req);
    if (guard) return guard;
    return {
      status: 200,
      body: {
        collection: "mascarade",
        documents: 1024,
        embedding_model: "bge-m3",
        status: "ok",
      },
    };
  },

  "GET /api/users": (req) => {
    const guard = authGuard(req);
    if (guard) return guard;
    // Simuler un opérateur (pas admin) → 403
    const token = getAuth(req);
    if (token === "mock-operator-token-32chars") {
      return { status: 403, body: { error: "Accès réservé aux administrateurs" } };
    }
    return { status: 200, body: [{ id: 1, email: "admin@mascarade.local", role_id: 1 }] };
  },
};

const server = http.createServer((req, res) => {
  const method = req.method;
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const pathname = url.pathname;
  const key = `${method} ${pathname}`;

  // CORS preflight
  if (method === "OPTIONS") {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
      "Access-Control-Allow-Headers": "Authorization,Content-Type,Cookie",
    });
    res.end();
    return;
  }

  let body = "";
  req.on("data", (chunk) => { body += chunk; });
  req.on("end", () => {
    let parsedBody = null;
    try { parsedBody = JSON.parse(body); } catch { /* pas de JSON body */ }

    const handler = routes[key];
    if (!handler) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: `Route non trouvée: ${key}` }));
      return;
    }

    const { status, body: responseBody } = handler(req, parsedBody);
    res.writeHead(status, {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    });
    res.end(JSON.stringify(responseBody));
  });
});

server.listen(PORT, () => {
  console.log(`[mock-api] Serveur démarré sur http://localhost:${PORT}`);
});

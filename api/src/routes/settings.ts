import { Hono, type Context } from "hono";

const settings = new Hono();
const OPS_AGENT_URL = (process.env.OPS_AGENT_URL || "http://ops-agent:9200").replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 15_000;

type RuntimeSecretMutationResponse = {
  status: string;
  message?: string;
  client_token?: string;
  generated_value?: string;
  updated_env?: string[];
  cleared_env?: string[];
};

type JsonBody = Record<string, unknown> | null;

function parseJsonBody(text: string): JsonBody {
  if (!text.trim()) {
    return null;
  }
  try {
    const parsed = JSON.parse(text);
    return typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function requestHeaders(c: Context, body?: unknown): Headers {
  const headers = new Headers();
  const authHeader = c.req.header("Authorization");
  const cookieHeader = c.req.header("Cookie");
  if (authHeader) {
    headers.set("Authorization", authHeader);
  }
  if (cookieHeader) {
    headers.set("Cookie", cookieHeader);
  }
  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

function jsonWithStatus(c: Context, body: Record<string, unknown>, status: number) {
  return c.newResponse(JSON.stringify(body), status as any, {
    "Content-Type": "application/json",
  });
}

async function proxyOpsAgent(
  c: Context,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(`${OPS_AGENT_URL}${path}`, {
      ...init,
      headers: requestHeaders(c, init.body),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

function syncRuntimeEnvFromUpdate(values: Record<string, string>) {
  for (const [key, value] of Object.entries(values)) {
    process.env[key] = value;
  }
}

function syncRuntimeEnvFromClear(fields: string[]) {
  for (const key of fields) {
    process.env[key] = "";
  }
}

settings.get("/runtime-secrets", async (c) => {
  try {
    const upstream = await proxyOpsAgent(c, "/runtime-secrets/status");
    const text = await upstream.text();
    const body = parseJsonBody(text);
    if (!upstream.ok) {
      return jsonWithStatus(c, body || { error: text || "Ops Agent request failed" }, upstream.status);
    }
    return c.json(body || { groups: [] });
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Ops Agent request failed" },
      503,
    );
  }
});

settings.put("/runtime-secrets/:groupName", async (c) => {
  try {
    const groupName = c.req.param("groupName");
    const body = (await c.req.json().catch(() => ({}))) as { values?: Record<string, string> };
    const values = body.values && typeof body.values === "object" ? body.values : {};
    const upstream = await proxyOpsAgent(c, `/runtime-secrets/${encodeURIComponent(groupName)}`, {
      method: "PUT",
      body: JSON.stringify({ values }),
    });
    const text = await upstream.text();
    const json = parseJsonBody(text);
    if (!upstream.ok) {
      return jsonWithStatus(c, json || { error: text || "Ops Agent request failed" }, upstream.status);
    }
    syncRuntimeEnvFromUpdate(values);
    return c.json(json || { status: "ok" });
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Ops Agent request failed" },
      503,
    );
  }
});

settings.post("/runtime-secrets/:groupName/clear", async (c) => {
  try {
    const groupName = c.req.param("groupName");
    const body = (await c.req.json().catch(() => ({}))) as { fields?: string[] };
    const fields = Array.isArray(body.fields) ? body.fields.map((field) => String(field)) : undefined;
    const upstream = await proxyOpsAgent(c, `/runtime-secrets/${encodeURIComponent(groupName)}/clear`, {
      method: "POST",
      body: JSON.stringify(fields ? { fields } : {}),
    });
    const text = await upstream.text();
    const json = parseJsonBody(text);
    if (!upstream.ok) {
      return jsonWithStatus(c, json || { error: text || "Ops Agent request failed" }, upstream.status);
    }
    const response = (json || { status: "ok" }) as RuntimeSecretMutationResponse;
    syncRuntimeEnvFromClear(response.cleared_env || fields || []);
    return c.json(response);
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Ops Agent request failed" },
      503,
    );
  }
});

settings.post("/runtime-secrets/:groupName/generate", async (c) => {
  try {
    const groupName = c.req.param("groupName");
    const upstream = await proxyOpsAgent(c, `/runtime-secrets/${encodeURIComponent(groupName)}/generate`, {
      method: "POST",
    });
    const text = await upstream.text();
    const json = parseJsonBody(text);
    if (!upstream.ok) {
      return jsonWithStatus(c, json || { error: text || "Ops Agent request failed" }, upstream.status);
    }
    const response = (json || { status: "ok" }) as RuntimeSecretMutationResponse;
    if (response.generated_value) {
      process.env.MASCARADE_API_KEY = response.generated_value;
    }
    return c.json(response);
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Ops Agent request failed" },
      503,
    );
  }
});

export { settings };

import { randomUUID } from "node:crypto";
import { Hono, type Context } from "hono";
import * as oidc from "openid-client";
import {
  getGitHubDispatchAccessToken,
  normalizeGitHubDispatchAuthMode,
} from "../lib/githubDispatchAuth.js";

const settings = new Hono();
const OPS_AGENT_URL = (process.env.OPS_AGENT_URL || "http://ops-agent:9200").replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 15_000;
const NOTION_OAUTH_STATE_COOKIE = "mascarade_notion_oauth_state";
const NOTION_OAUTH_STATE_MAX_AGE = 10 * 60;
const NOTION_AUTHORIZATION_ENDPOINT =
  process.env.NOTION_OAUTH_AUTHORIZATION_ENDPOINT || "https://api.notion.com/v1/oauth/authorize";
const NOTION_TOKEN_ENDPOINT =
  process.env.NOTION_OAUTH_TOKEN_ENDPOINT || "https://api.notion.com/v1/oauth/token";
const NOTION_ISSUER = "https://api.notion.com/v1";

type RuntimeSecretMutationResponse = {
  status: string;
  message?: string;
  client_token?: string;
  generated_value?: string;
  updated_env?: string[];
  cleared_env?: string[];
};

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

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

function cookieValue(cookieHeader: string | undefined, name: string): string {
  if (!cookieHeader) {
    return "";
  }
  const match = cookieHeader.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}

function notionOAuthRedirectUri(c: Context): string {
  const override = String(process.env.NOTION_OAUTH_REDIRECT_URI || "").trim();
  if (override) {
    return override;
  }
  const current = new URL(c.req.url);
  return `${current.origin}/api/settings/oauth/notion/callback`;
}

function notionOAuthConfig() {
  const clientId = String(process.env.NOTION_OAUTH_CLIENT_ID || "").trim();
  const clientSecret = String(process.env.NOTION_OAUTH_CLIENT_SECRET || "").trim();
  if (!clientId || !clientSecret) {
    throw new Error("Missing NOTION_OAUTH_CLIENT_ID or NOTION_OAUTH_CLIENT_SECRET");
  }
  return new oidc.Configuration(
    {
      issuer: NOTION_ISSUER,
      authorization_endpoint: String(
        process.env.NOTION_OAUTH_AUTHORIZATION_ENDPOINT || NOTION_AUTHORIZATION_ENDPOINT,
      ).trim(),
      token_endpoint: String(
        process.env.NOTION_OAUTH_TOKEN_ENDPOINT || NOTION_TOKEN_ENDPOINT,
      ).trim(),
    },
    clientId,
    undefined,
    oidc.ClientSecretBasic(clientSecret),
  );
}

function popupResponse(message: string, ok: boolean, extraHeaders?: HeadersInit): Response {
  const payload = JSON.stringify({
    type: "mascarade-oauth-result",
    provider: "notion",
    ok,
    message,
  }).replaceAll("<", "\\u003c");
  const safeMessage = escapeHtml(message);
  const body = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Mascarade OAuth</title>
  </head>
  <body style="font-family: ui-monospace, SFMono-Regular, Menlo, monospace; background:#050505; color:#f5d08a; padding:24px;">
    <p>${ok ? "OAuth linked." : "OAuth failed."}</p>
    <p>${safeMessage}</p>
    <script>
      try {
        if (window.opener && window.opener !== window) {
          window.opener.postMessage(${payload}, window.location.origin);
        }
      } catch {}
      setTimeout(() => window.close(), 120);
    </script>
  </body>
</html>`;
  return new Response(body, {
    status: ok ? 200 : 400,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      ...(extraHeaders || {}),
    },
  });
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

async function proxyOpsAgentJson(
  c: Context,
  path: string,
  init: RequestInit = {},
): Promise<{ upstream: Response; text: string; json: JsonBody }> {
  const upstream = await proxyOpsAgent(c, path, init);
  const text = await upstream.text();
  return { upstream, text, json: parseJsonBody(text) };
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
    const { upstream, text, json } = await proxyOpsAgentJson(c, "/runtime-secrets/status");
    if (!upstream.ok) {
      return jsonWithStatus(c, json || { error: text || "Ops Agent request failed" }, upstream.status);
    }
    return c.json(json || { groups: [] });
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
    const { upstream, text, json } = await proxyOpsAgentJson(
      c,
      `/runtime-secrets/${encodeURIComponent(groupName)}`,
      {
        method: "PUT",
        body: JSON.stringify({ values }),
      },
    );
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
    const { upstream, text, json } = await proxyOpsAgentJson(
      c,
      `/runtime-secrets/${encodeURIComponent(groupName)}/clear`,
      {
        method: "POST",
        body: JSON.stringify(fields ? { fields } : {}),
      },
    );
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
    const { upstream, text, json } = await proxyOpsAgentJson(
      c,
      `/runtime-secrets/${encodeURIComponent(groupName)}/generate`,
      { method: "POST" },
    );
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

settings.get("/runtime-secrets/notion/oauth/start", async (c) => {
  try {
    const config = notionOAuthConfig();
    const redirectUri = notionOAuthRedirectUri(c);
    const state = `${randomUUID()}.${oidc.randomState()}`;
    const authorizationUrl = oidc.buildAuthorizationUrl(config, {
      owner: "user",
      redirect_uri: redirectUri,
      response_type: "code",
      state,
    });
    const secure = new URL(c.req.url).protocol === "https:" ? "; Secure" : "";
    return c.newResponse(null, 302 as any, {
      Location: authorizationUrl.href,
      "Set-Cookie": `${NOTION_OAUTH_STATE_COOKIE}=${encodeURIComponent(state)}; HttpOnly; SameSite=Lax; Path=/api/settings/oauth/notion/callback; Max-Age=${NOTION_OAUTH_STATE_MAX_AGE}${secure}`,
    });
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Unable to start Notion OAuth" },
      400,
    );
  }
});

settings.get("/oauth/notion/callback", async (c) => {
  const secure = new URL(c.req.url).protocol === "https:" ? "; Secure" : "";
  const clearCookie = `${NOTION_OAUTH_STATE_COOKIE}=; HttpOnly; SameSite=Lax; Path=/api/settings/oauth/notion/callback; Max-Age=0${secure}`;
  try {
    const expectedState = cookieValue(c.req.header("Cookie"), NOTION_OAUTH_STATE_COOKIE);
    if (!expectedState) {
      return popupResponse("Missing OAuth state cookie", false, { "Set-Cookie": clearCookie });
    }
    const config = notionOAuthConfig();
    const redirectUri = notionOAuthRedirectUri(c);
    const callbackUrl = new URL(c.req.url);
    const returnedState = callbackUrl.searchParams.get("state") || "";
    if (!returnedState || returnedState !== expectedState) {
      return popupResponse("OAuth state mismatch", false, { "Set-Cookie": clearCookie });
    }
    const oauthError = callbackUrl.searchParams.get("error");
    if (oauthError) {
      const message = callbackUrl.searchParams.get("error_description") || oauthError;
      return popupResponse(message, false, { "Set-Cookie": clearCookie });
    }

    const tokens = await oidc.authorizationCodeGrant(
      config,
      callbackUrl,
      { expectedState },
      { redirect_uri: redirectUri },
    );
    const accessToken = String(tokens.access_token || "").trim();
    if (!accessToken) {
      return popupResponse("Notion OAuth returned no access token", false, { "Set-Cookie": clearCookie });
    }

    const values: Record<string, string> = {
      NOTION_AUTH_MODE: "oauth_oidc",
      NOTION_API_KEY: "",
      NOTION_OAUTH_ACCESS_TOKEN: accessToken,
      NOTION_OAUTH_REFRESH_TOKEN: String(tokens.refresh_token || "").trim(),
      NOTION_OAUTH_REDIRECT_URI: redirectUri,
      NOTION_OAUTH_EXPIRES_AT:
        typeof tokens.expires_in === "number" && Number.isFinite(tokens.expires_in)
          ? new Date(Date.now() + tokens.expires_in * 1000).toISOString()
          : "",
      NOTION_OAUTH_WORKSPACE_NAME: String((tokens as Record<string, unknown>).workspace_name || "").trim(),
    };
    const { upstream, text, json } = await proxyOpsAgentJson(c, "/runtime-secrets/notion", {
      method: "PUT",
      body: JSON.stringify({ values }),
    });
    if (!upstream.ok) {
      const detail =
        (json && typeof json.error === "string" && json.error) ||
        text ||
        `Ops Agent request failed (${upstream.status})`;
      return popupResponse(detail, false, { "Set-Cookie": clearCookie });
    }

    syncRuntimeEnvFromUpdate(values);
    return popupResponse("Notion OAuth linked", true, { "Set-Cookie": clearCookie });
  } catch (error) {
    return popupResponse(
      error instanceof Error ? error.message : "Notion OAuth callback failed",
      false,
      { "Set-Cookie": clearCookie },
    );
  }
});

settings.post("/runtime-secrets/github-dispatch/app-token", async (c) => {
  try {
    if (normalizeGitHubDispatchAuthMode(process.env.GITHUB_DISPATCH_AUTH_MODE) !== "app") {
      return c.json({ error: "GitHub dispatch auth mode is not 'app'" }, 400);
    }
    const auth = await getGitHubDispatchAccessToken(process.env);
    return c.json({
      status: "ok",
      auth_mode: auth.authMode,
      token: auth.token,
      expires_at: auth.expiresAt,
    });
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "GitHub App token refresh failed" },
      400,
    );
  }
});

export { settings };

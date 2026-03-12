import { randomUUID } from "node:crypto";
import { Hono, type Context } from "hono";
import { OAuth2Client } from "google-auth-library";
import * as oidc from "openid-client";
import {
  getGitHubDispatchAccessToken,
  normalizeGitHubDispatchAuthMode,
} from "../lib/githubDispatchAuth.js";
import { isSecureRequest, noStoreHeaders } from "../lib/request-security.js";

const settings = new Hono();
const OPS_AGENT_URL = (process.env.OPS_AGENT_URL || "http://ops-agent:9200").replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 15_000;
const HUGGINGFACE_OAUTH_STATE_COOKIE = "mascarade_huggingface_oauth_state";
const GOOGLE_OAUTH_STATE_COOKIE = "mascarade_google_oauth_state";
const PROVIDER_OAUTH_STATE_MAX_AGE = 10 * 60;
const HUGGINGFACE_AUTHORIZATION_ENDPOINT =
  process.env.HUGGINGFACE_OAUTH_AUTHORIZATION_ENDPOINT || "https://huggingface.co/oauth/authorize";
const HUGGINGFACE_TOKEN_ENDPOINT =
  process.env.HUGGINGFACE_OAUTH_TOKEN_ENDPOINT || "https://huggingface.co/oauth/token";
const HUGGINGFACE_ISSUER = "https://huggingface.co";
const GOOGLE_AUTHORIZATION_ENDPOINT =
  process.env.GOOGLE_OAUTH_AUTHORIZATION_ENDPOINT || "https://accounts.google.com/o/oauth2/v2/auth";
const GOOGLE_TOKEN_ENDPOINT =
  process.env.GOOGLE_OAUTH_TOKEN_ENDPOINT || "https://oauth2.googleapis.com/token";
const GOOGLE_OAUTH_SCOPES = (process.env.GOOGLE_OAUTH_SCOPES ||
  "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/generative-language.retriever")
  .split(/[,\s]+/)
  .map((scope) => scope.trim())
  .filter(Boolean);

type RuntimeSecretMutationResponse = {
  status: string;
  message?: string;
  client_token?: string;
  generated_value?: string;
  extra_info?: string;
  updated_env?: string[];
  cleared_env?: string[];
};
const SENSITIVE_KEY_RE = /(token|secret|api[_-]?key|password|authorization)/i;
const GENERATED_VALUE_KEY_RE = /^(generated[_-]?value|generatedValue)$/i;

settings.use("*", async (c, next) => {
  await next();
  for (const [header, value] of Object.entries(noStoreHeaders())) {
    c.header(header, value);
  }
});

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

function maskSecret(value: string): string {
  const token = String(value || "").trim();
  if (!token) {
    return "";
  }
  if (token.length <= 8) {
    return "***";
  }
  return `${token.slice(0, 4)}***${token.slice(-4)}`;
}

function sanitizeErrorMessage(value: string): string {
  const message = String(value || "").trim();
  if (!message) {
    return "";
  }
  return message
    .replace(
      /\b(Bearer\s+)([A-Za-z0-9._~\-]{8,})\b/gi,
      (_match, prefix: string, token: string) => `${prefix}${maskSecret(token)}`,
    )
    .replace(
      /\b(token|secret|api[_-]?key|password|authorization)\b\s*[:=]\s*([^\s,;]+)/gi,
      (_match, key: string, token: string) => `${key}=${maskSecret(token)}`,
    );
}

function sanitizeSensitivePayload(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeSensitivePayload(item));
  }
  if (!value || typeof value !== "object") {
    return value;
  }
  const input = value as Record<string, unknown>;
  const output: Record<string, unknown> = {};
  for (const [key, raw] of Object.entries(input)) {
    if (GENERATED_VALUE_KEY_RE.test(key)) {
      if (typeof raw === "string" && raw.trim()) {
        output.generated_value_masked = maskSecret(raw);
      }
      continue;
    }
    if (typeof raw === "string" && SENSITIVE_KEY_RE.test(key)) {
      output[key] = maskSecret(raw);
      continue;
    }
    output[key] = sanitizeSensitivePayload(raw);
  }
  return output;
}

function cookieValue(cookieHeader: string | undefined, name: string): string {
  if (!cookieHeader) {
    return "";
  }
  const match = cookieHeader.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}

function providerOAuthRedirectUri(c: Context, provider: string): string {
  const envName = `${provider.toUpperCase().replaceAll("-", "_")}_OAUTH_REDIRECT_URI`;
  const override = String(process.env[envName] || "").trim();
  if (override) {
    return override;
  }
  const current = new URL(c.req.url);
  return `${current.origin}/api/settings/oauth/${provider}/callback`;
}

function huggingFaceOAuthConfig() {
  const clientId = String(process.env.HUGGINGFACE_OAUTH_CLIENT_ID || "").trim();
  const clientSecret = String(process.env.HUGGINGFACE_OAUTH_CLIENT_SECRET || "").trim();
  if (!clientId || !clientSecret) {
    throw new Error("Missing HUGGINGFACE_OAUTH_CLIENT_ID or HUGGINGFACE_OAUTH_CLIENT_SECRET");
  }
  return new oidc.Configuration(
    {
      issuer: HUGGINGFACE_ISSUER,
      authorization_endpoint: String(
        process.env.HUGGINGFACE_OAUTH_AUTHORIZATION_ENDPOINT || HUGGINGFACE_AUTHORIZATION_ENDPOINT,
      ).trim(),
      token_endpoint: String(
        process.env.HUGGINGFACE_OAUTH_TOKEN_ENDPOINT || HUGGINGFACE_TOKEN_ENDPOINT,
      ).trim(),
    },
    clientId,
    undefined,
    oidc.ClientSecretBasic(clientSecret),
  );
}

function googleOAuthClient(c: Context): OAuth2Client {
  const clientId = String(process.env.GOOGLE_OAUTH_CLIENT_ID || "").trim();
  const clientSecret = String(process.env.GOOGLE_OAUTH_CLIENT_SECRET || "").trim();
  if (!clientId || !clientSecret) {
    throw new Error("Missing GOOGLE_OAUTH_CLIENT_ID or GOOGLE_OAUTH_CLIENT_SECRET");
  }
  return new OAuth2Client({
    clientId,
    clientSecret,
    redirectUri: providerOAuthRedirectUri(c, "google"),
  });
}

function popupResponse(
  message: string,
  ok: boolean,
  provider: string,
  extraHeaders?: HeadersInit,
): Response {
  const payload = JSON.stringify({
    type: "mascarade-oauth-result",
    provider,
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
      ...noStoreHeaders(),
      ...(extraHeaders || {}),
    },
  });
}

function requestHeaders(c: Context, body?: unknown): Headers {
  const headers = new Headers();
  const authHeader = c.req.header("Authorization");
  if (authHeader) {
    headers.set("Authorization", authHeader);
  }
  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

function jsonWithStatus(c: Context, body: Record<string, unknown>, status: number) {
  const sanitized = (sanitizeSensitivePayload(body) as Record<string, unknown>) || {};
  return c.newResponse(JSON.stringify(sanitized), status as any, {
    "Content-Type": "application/json",
    ...noStoreHeaders(),
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

function syncProviderEnvFromUpdate(values: Record<string, string>) {
  for (const [key, value] of Object.entries(values)) {
    process.env[key] = value;
  }
}

async function persistProviderValues(
  c: Context,
  providerName: string,
  keys: Record<string, string>,
): Promise<{ error?: string }> {
  const { upstream, json } = await proxyOpsAgentJson(
    c,
    `/providers/${encodeURIComponent(providerName)}`,
    {
      method: "PUT",
      body: JSON.stringify({ keys }),
    },
  );
  if (!upstream.ok) {
    const upstreamError =
      (json && typeof json.error === "string" && sanitizeErrorMessage(json.error)) || "";
    return {
      error: upstreamError || `Ops Agent request failed (${upstream.status})`,
    };
  }
  syncProviderEnvFromUpdate(keys);
  return {};
}

settings.get("/runtime-secrets", async (c) => {
  try {
    const { upstream, text, json } = await proxyOpsAgentJson(c, "/runtime-secrets/status");
    if (!upstream.ok) {
      return jsonWithStatus(c, json || { error: text || "Ops Agent request failed" }, upstream.status);
    }
    return c.json((sanitizeSensitivePayload(json || { groups: [] }) as Record<string, unknown>) || { groups: [] });
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
    return c.json((sanitizeSensitivePayload(json || { status: "ok" }) as Record<string, unknown>) || { status: "ok" });
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
    return c.json((sanitizeSensitivePayload(response) as Record<string, unknown>) || { status: "ok" });
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
    const { generated_value: _generatedValue, ...publicResponse } = response;
    return c.json((sanitizeSensitivePayload(publicResponse) as Record<string, unknown>) || { status: "ok" });
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Ops Agent request failed" },
      503,
    );
  }
});

settings.post("/runtime-secrets/knowledge-base/bootstrap-memos", async (c) => {
  try {
    const { upstream, text, json } = await proxyOpsAgentJson(
      c,
      "/runtime-secrets/knowledge-base/bootstrap-memos",
      { method: "POST" },
    );
    if (!upstream.ok) {
      return jsonWithStatus(c, json || { error: text || "Ops Agent request failed" }, upstream.status);
    }
    const response = (json || {}) as RuntimeSecretMutationResponse;
    return c.json((sanitizeSensitivePayload(response) as Record<string, unknown>) || { status: "ok" });
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Ops Agent request failed" },
      503,
    );
  }
});

settings.get("/providers/huggingface/oauth/start", async (c) => {
  try {
    const config = huggingFaceOAuthConfig();
    const redirectUri = providerOAuthRedirectUri(c, "huggingface");
    const state = `${randomUUID()}.${oidc.randomState()}`;
    const authorizationUrl = oidc.buildAuthorizationUrl(config, {
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "openid profile inference-api",
      state,
    });
    const secure = isSecureRequest(c.req) ? "; Secure" : "";
    return c.newResponse(null, 302 as any, {
      Location: authorizationUrl.href,
      "Set-Cookie": `${HUGGINGFACE_OAUTH_STATE_COOKIE}=${encodeURIComponent(state)}; HttpOnly; SameSite=Lax; Path=/api/settings/oauth/huggingface/callback; Max-Age=${PROVIDER_OAUTH_STATE_MAX_AGE}${secure}`,
    });
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Unable to start HuggingFace OAuth" },
      400,
    );
  }
});

settings.get("/oauth/huggingface/callback", async (c) => {
  const secure = isSecureRequest(c.req) ? "; Secure" : "";
  const clearCookie = `${HUGGINGFACE_OAUTH_STATE_COOKIE}=; HttpOnly; SameSite=Lax; Path=/api/settings/oauth/huggingface/callback; Max-Age=0${secure}`;
  try {
    const expectedState = cookieValue(c.req.header("Cookie"), HUGGINGFACE_OAUTH_STATE_COOKIE);
    if (!expectedState) {
      return popupResponse("Missing OAuth state cookie", false, "huggingface", { "Set-Cookie": clearCookie });
    }
    const config = huggingFaceOAuthConfig();
    const redirectUri = providerOAuthRedirectUri(c, "huggingface");
    const callbackUrl = new URL(c.req.url);
    const returnedState = callbackUrl.searchParams.get("state") || "";
    if (!returnedState || returnedState !== expectedState) {
      return popupResponse("OAuth state mismatch", false, "huggingface", { "Set-Cookie": clearCookie });
    }
    const oauthError = callbackUrl.searchParams.get("error");
    if (oauthError) {
      const message = callbackUrl.searchParams.get("error_description") || oauthError;
      return popupResponse(message, false, "huggingface", { "Set-Cookie": clearCookie });
    }

    const tokens = await oidc.authorizationCodeGrant(
      config,
      callbackUrl,
      { expectedState },
      { redirect_uri: redirectUri },
    );
    const accessToken = String(tokens.access_token || "").trim();
    if (!accessToken) {
      return popupResponse("HuggingFace OAuth returned no access token", false, "huggingface", { "Set-Cookie": clearCookie });
    }

    const values: Record<string, string> = {
      HUGGINGFACE_AUTH_MODE: "oauth_oidc",
      HUGGINGFACE_API_KEY: "",
      HUGGINGFACE_OAUTH_ACCESS_TOKEN: accessToken,
      HUGGINGFACE_OAUTH_REFRESH_TOKEN: String(tokens.refresh_token || "").trim(),
      HUGGINGFACE_OAUTH_EXPIRES_AT:
        typeof tokens.expires_in === "number" && Number.isFinite(tokens.expires_in)
          ? new Date(Date.now() + tokens.expires_in * 1000).toISOString()
          : "",
    };
    const persisted = await persistProviderValues(c, "huggingface", values);
    if (persisted.error) {
      return popupResponse(persisted.error, false, "huggingface", { "Set-Cookie": clearCookie });
    }

    return popupResponse("HuggingFace OAuth linked", true, "huggingface", { "Set-Cookie": clearCookie });
  } catch (error) {
    return popupResponse(
      error instanceof Error ? error.message : "HuggingFace OAuth callback failed",
      false,
      "huggingface",
      { "Set-Cookie": clearCookie },
    );
  }
});

settings.get("/providers/google/oauth/start", async (c) => {
  try {
    const client = googleOAuthClient(c);
    const state = `${randomUUID()}.${Math.random().toString(36).slice(2)}`;
    const authorizationUrl = client.generateAuthUrl({
      access_type: "offline",
      include_granted_scopes: true,
      prompt: "consent",
      scope: GOOGLE_OAUTH_SCOPES,
      state,
    });
    const secure = isSecureRequest(c.req) ? "; Secure" : "";
    return c.newResponse(null, 302 as any, {
      Location: authorizationUrl,
      "Set-Cookie": `${GOOGLE_OAUTH_STATE_COOKIE}=${encodeURIComponent(state)}; HttpOnly; SameSite=Lax; Path=/api/settings/oauth/google/callback; Max-Age=${PROVIDER_OAUTH_STATE_MAX_AGE}${secure}`,
    });
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Unable to start Google OAuth" },
      400,
    );
  }
});

settings.get("/oauth/google/callback", async (c) => {
  const secure = isSecureRequest(c.req) ? "; Secure" : "";
  const clearCookie = `${GOOGLE_OAUTH_STATE_COOKIE}=; HttpOnly; SameSite=Lax; Path=/api/settings/oauth/google/callback; Max-Age=0${secure}`;
  try {
    const expectedState = cookieValue(c.req.header("Cookie"), GOOGLE_OAUTH_STATE_COOKIE);
    if (!expectedState) {
      return popupResponse("Missing OAuth state cookie", false, "google", { "Set-Cookie": clearCookie });
    }
    const callbackUrl = new URL(c.req.url);
    const returnedState = callbackUrl.searchParams.get("state") || "";
    if (!returnedState || returnedState !== expectedState) {
      return popupResponse("OAuth state mismatch", false, "google", { "Set-Cookie": clearCookie });
    }
    const oauthError = callbackUrl.searchParams.get("error");
    if (oauthError) {
      const message = callbackUrl.searchParams.get("error_description") || oauthError;
      return popupResponse(message, false, "google", { "Set-Cookie": clearCookie });
    }
    const code = callbackUrl.searchParams.get("code") || "";
    if (!code) {
      return popupResponse("Missing Google authorization code", false, "google", { "Set-Cookie": clearCookie });
    }

    const client = googleOAuthClient(c);
    const tokenResponse = await client.getToken(code);
    const accessToken = String(tokenResponse.tokens.access_token || "").trim();
    if (!accessToken) {
      return popupResponse("Google OAuth returned no access token", false, "google", { "Set-Cookie": clearCookie });
    }

    const values: Record<string, string> = {
      GOOGLE_AUTH_MODE: "oauth_oidc",
      GOOGLE_API_KEY: "",
      GOOGLE_OAUTH_ACCESS_TOKEN: accessToken,
      GOOGLE_OAUTH_REFRESH_TOKEN: String(tokenResponse.tokens.refresh_token || "").trim(),
      GOOGLE_OAUTH_EXPIRES_AT:
        typeof tokenResponse.tokens.expiry_date === "number" && Number.isFinite(tokenResponse.tokens.expiry_date)
          ? new Date(tokenResponse.tokens.expiry_date).toISOString()
          : "",
    };
    const persisted = await persistProviderValues(c, "google", values);
    if (persisted.error) {
      return popupResponse(persisted.error, false, "google", { "Set-Cookie": clearCookie });
    }

    return popupResponse("Google OAuth linked", true, "google", { "Set-Cookie": clearCookie });
  } catch (error) {
    return popupResponse(
      error instanceof Error ? error.message : "Google OAuth callback failed",
      false,
      "google",
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
      token_masked: maskSecret(auth.token),
      token_present: Boolean(String(auth.token || "").trim()),
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

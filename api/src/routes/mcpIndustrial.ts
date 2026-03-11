import { Hono } from "hono";

const industrialMcp = new Hono();

const COCKPIT_BASE_URL = (process.env.AGENT_FACTORY_COCKPIT_URL || "http://agent-factory-cockpit:4173").replace(/\/$/, "");
const COCKPIT_MCP_PATH = process.env.AGENT_FACTORY_COCKPIT_MCP_PATH || "/mcp/industrial";
const REQUEST_TIMEOUT_MS = parseInt(process.env.AGENT_FACTORY_COCKPIT_MCP_TIMEOUT_MS || "30000", 10);
const STATIC_PROXY_GROUPS = String(process.env.AGENT_FACTORY_COCKPIT_PROXY_GROUPS || "").trim();

function cockpitMcpUrl(pathSuffix = ""): string {
  return `${COCKPIT_BASE_URL}${COCKPIT_MCP_PATH}${pathSuffix}`;
}

function forwardedIdentityHeaders(headers: Headers): Record<string, string> {
  const forwardedEmail =
    headers.get("Cf-Access-Authenticated-User-Email") ||
    headers.get("X-Forwarded-Email") ||
    headers.get("X-Auth-Request-Email") ||
    "";
  const forwardedUser =
    headers.get("X-Forwarded-User") ||
    headers.get("X-Auth-Request-User") ||
    forwardedEmail ||
    "mascarade-platform";
  const forwardedGroups =
    headers.get("X-Forwarded-Groups") ||
    headers.get("X-Auth-Request-Groups") ||
    STATIC_PROXY_GROUPS;
  const forwarded: Record<string, string> = {
    "X-Forwarded-User": forwardedUser,
    "X-Forwarded-Email": forwardedEmail || forwardedUser,
  };
  if (forwardedGroups) {
    forwarded["X-Forwarded-Groups"] = forwardedGroups;
  }
  return forwarded;
}

async function proxyCockpitMcp(request: Request, pathSuffix = ""): Promise<Response> {
  const outgoingHeaders = new Headers(forwardedIdentityHeaders(request.headers));
  const contentType = request.headers.get("Content-Type");
  if (contentType) {
    outgoingHeaders.set("Content-Type", contentType);
  }
  const init: RequestInit = {
    method: request.method,
    headers: outgoingHeaders,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }
  const upstream = await fetch(cockpitMcpUrl(pathSuffix), init);
  const body = request.method === "HEAD" ? null : await upstream.text();
  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get("Content-Type");
  if (upstreamContentType) {
    responseHeaders.set("Content-Type", upstreamContentType);
  }
  return new Response(body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

industrialMcp.get("/", async (c) => proxyCockpitMcp(c.req.raw));

industrialMcp.get("/:serverKey", async (c) => {
  return proxyCockpitMcp(c.req.raw, `/${encodeURIComponent(c.req.param("serverKey"))}`);
});

industrialMcp.post("/:serverKey", async (c) => {
  return proxyCockpitMcp(c.req.raw, `/${encodeURIComponent(c.req.param("serverKey"))}`);
});

export { industrialMcp };

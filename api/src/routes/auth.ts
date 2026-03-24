import { Hono } from "hono";
import { validateToken } from "../lib/auth.js";
import {
  authUnavailableResponse,
  clearSessionCookie,
  isAuthConfigured,
  isValidConfiguredApiKey,
  makeSessionCookie,
} from "../middleware/auth.js";
import { isSecureRequest, noStoreHeaders } from "../lib/request-security.js";

const auth = new Hono();

auth.use("*", async (c, next) => {
  await next();
  for (const [header, value] of Object.entries(noStoreHeaders())) {
    c.header(header, value);
  }
});

auth.post("/session", async (c) => {
  const body = (await c.req.json().catch(() => ({}))) as {
    persist?: boolean;
    api_key?: string;
  };
  const authHeader = c.req.header("Authorization") || "";
  const tokenFromHeader = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";
  const tokenFromBody = String(body.api_key || "").trim();
  const token = tokenFromBody || tokenFromHeader;

  if (!isAuthConfigured()) {
    return c.json(authUnavailableResponse(), 503);
  }

  const validFromConfig = isValidConfiguredApiKey(token);
  const validFromDatabase = validFromConfig ? false : Boolean(await validateToken(token));
  if (!validFromConfig && !validFromDatabase) {
    return c.json({ error: "Token invalide ou manquant" }, 401);
  }

  const persist = Boolean(body.persist);
  const secure = isSecureRequest(c.req);

  c.header("Set-Cookie", makeSessionCookie(token, persist, secure));
  return c.json({ status: "ok" });
});

auth.delete("/session", (c) => {
  const secure = isSecureRequest(c.req);
  c.header("Set-Cookie", clearSessionCookie(secure));
  return c.json({ status: "ok" });
});

export { auth };

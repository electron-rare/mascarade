import { Hono } from "hono";
import {
  clearSessionCookie,
  isValidConfiguredApiKey,
  makeSessionCookie,
} from "../middleware/auth.js";

const auth = new Hono();

function secureRequest(url: string): boolean {
  try {
    return new URL(url).protocol === "https:";
  } catch {
    return false;
  }
}

auth.post("/session", async (c) => {
  const authHeader = c.req.header("Authorization") || "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";
  if (!isValidConfiguredApiKey(token)) {
    return c.json({ error: "Token invalide ou manquant" }, 401);
  }

  const body = (await c.req.json().catch(() => ({}))) as { persist?: boolean };
  const persist = Boolean(body.persist);
  const secure = secureRequest(c.req.url);

  c.header("Set-Cookie", makeSessionCookie(token, persist, secure));
  return c.json({ status: "ok" });
});

auth.delete("/session", (c) => {
  const secure = secureRequest(c.req.url);
  c.header("Set-Cookie", clearSessionCookie(secure));
  return c.json({ status: "ok" });
});

export { auth };

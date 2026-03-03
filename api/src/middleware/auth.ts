/**
 * Middleware d'authentification — Bearer token simple.
 * Si MASCARADE_API_KEY est vide, l'auth est désactivée.
 */

import type { MiddlewareHandler } from "hono";

const API_KEY = process.env.MASCARADE_API_KEY || "";

export const authMiddleware: MiddlewareHandler = async (c, next) => {
  if (!API_KEY) {
    return next();
  }

  const authHeader = c.req.header("Authorization");
  if (!authHeader || authHeader !== `Bearer ${API_KEY}`) {
    return c.json({ error: "Token invalide ou manquant" }, 401);
  }
  return next();
};

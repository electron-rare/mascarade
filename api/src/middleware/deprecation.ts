/**
 * Middleware de dépréciation — ajoute des headers HTTP pour signaler les endpoints dépréciés.
 * Suit le standard RFC 8594 (Deprecation header) et Sunset header.
 */

import type { Context, MiddlewareHandler, Next } from "hono";

export interface DeprecationConfig {
  /** Message de dépréciation à afficher */
  message: string;
  /** Date de retrait prévue (format ISO 8601) */
  sunsetDate?: string;
  /** URL de documentation ou endpoint de remplacement */
  link?: string;
  /** Version à partir de laquelle c'est déprécié */
  since?: string;
}

/**
 * Crée un middleware de dépréciation pour un endpoint spécifique.
 *
 * @param config Configuration de la dépréciation
 * @returns Middleware Hono
 *
 * @example
 * ```ts
 * app.use("/api/old-endpoint", deprecationMiddleware({
 *   message: "Use /v1/api/new-endpoint instead",
 *   sunsetDate: "2026-06-01T00:00:00Z",
 *   link: "/v1/api/new-endpoint",
 *   since: "1.0.0"
 * }));
 * ```
 */
export function deprecationMiddleware(config: DeprecationConfig): MiddlewareHandler {
  return async (c: Context, next: Next) => {
    // Ajouter le header Deprecation (RFC 8594)
    // true = déprécié, date = déprécié à partir de cette date
    c.header("Deprecation", "true");

    // Ajouter le header Warning (RFC 7234)
    const warningMessage = config.message || "This endpoint is deprecated";
    c.header("Warning", `299 - "${warningMessage}"`);

    // Ajouter le header Sunset si une date de retrait est prévue
    if (config.sunsetDate) {
      c.header("Sunset", config.sunsetDate);
    }

    // Ajouter le header Link si un endpoint de remplacement existe
    if (config.link) {
      c.header("Link", `<${config.link}>; rel="alternate"`);
    }

    // Ajouter un header custom pour la version
    if (config.since) {
      c.header("X-Deprecated-Since", config.since);
    }

    // Logger l'utilisation d'un endpoint déprécié
    const path = c.req.path;
    const method = c.req.method;
    console.warn(
      `[deprecation] ${method} ${path} - ${warningMessage}`,
      config.sunsetDate ? `(sunset: ${config.sunsetDate})` : "",
    );

    await next();
  };
}

/**
 * Crée un middleware de dépréciation basé sur des règles de patterns.
 * Permet de gérer plusieurs endpoints dépréciés avec une seule configuration.
 *
 * @param rules Map des patterns d'URL vers leur configuration de dépréciation
 * @returns Middleware Hono
 *
 * @example
 * ```ts
 * const rules = new Map([
 *   ["/api/agents", { message: "Use /v1/api/agents", link: "/v1/api/agents" }],
 *   ["/api/cluster", { message: "Use /v1/api/cluster", link: "/v1/api/cluster" }],
 * ]);
 * app.use("*", deprecationByPattern(rules));
 * ```
 */
export function deprecationByPattern(
  rules: Map<string, DeprecationConfig>,
): MiddlewareHandler {
  return async (c: Context, next: Next) => {
    const path = c.req.path;

    // Chercher une règle correspondante
    for (const [pattern, config] of rules) {
      // Support des patterns simples (exact match ou prefix)
      const isMatch = path === pattern || path.startsWith(pattern + "/");

      if (isMatch) {
        // Appliquer la dépréciation
        c.header("Deprecation", "true");
        c.header("Warning", `299 - "${config.message}"`);

        if (config.sunsetDate) {
          c.header("Sunset", config.sunsetDate);
        }
        if (config.link) {
          c.header("Link", `<${config.link}>; rel="alternate"`);
        }
        if (config.since) {
          c.header("X-Deprecated-Since", config.since);
        }

        console.warn(
          `[deprecation] ${c.req.method} ${path} - ${config.message}`,
          config.sunsetDate ? `(sunset: ${config.sunsetDate})` : "",
        );

        break; // Première règle trouvée seulement
      }
    }

    await next();
  };
}

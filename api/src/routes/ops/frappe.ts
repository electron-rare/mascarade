import { Hono } from "hono";
import { timedProbe, timedJson, FRAPPE_CRM_URL, frappeCrmAuthHeader } from "./_shared.js";

const frappeRoutes = new Hono();

/**
 * GET /api/ops/frappe
 * Snapshot de santé Frappe CRM + ERPNext pour l'opérateur Electron Rare.
 * Fournit: ping, counts leads/deals/quotations, container health.
 */
frappeRoutes.get("/frappe", async (c) => {
  const authHeaders = frappeCrmAuthHeader();
  const hasAuth = Object.keys(authHeaders).length > 0;

  const [ping, leads, deals, quotations] = await Promise.all([
    timedProbe("frappe-crm", `${FRAPPE_CRM_URL}/api/method/ping`, 2000),
    hasAuth
      ? timedJson(
          `${FRAPPE_CRM_URL}/api/resource/CRM%20Lead?limit_page_length=0&fields=%5B%22name%22%5D`,
          3000,
          authHeaders,
        )
      : Promise.resolve({ ok: false, json: null, error: "no auth configured", status: 0, latencyMs: 0 }),
    hasAuth
      ? timedJson(
          `${FRAPPE_CRM_URL}/api/resource/CRM%20Deal?limit_page_length=0&fields=%5B%22name%22%5D`,
          3000,
          authHeaders,
        )
      : Promise.resolve({ ok: false, json: null, error: "no auth configured", status: 0, latencyMs: 0 }),
    hasAuth
      ? timedJson(
          `${FRAPPE_CRM_URL}/api/resource/Quotation?limit_page_length=0&fields=%5B%22name%22%5D`,
          3000,
          authHeaders,
        )
      : Promise.resolve({ ok: false, json: null, error: "no auth configured", status: 0, latencyMs: 0 }),
  ]);

  const leadCount = Array.isArray(leads.json?.data) ? leads.json.data.length : null;
  const dealCount = Array.isArray(deals.json?.data) ? deals.json.data.length : null;
  const quotationCount = Array.isArray(quotations.json?.data) ? quotations.json.data.length : null;
  const dataAvailable = hasAuth && leadCount !== null && dealCount !== null && quotationCount !== null;

  return c.json({
    ok: ping.ok,
    timestamp: new Date().toISOString(),
    url: FRAPPE_CRM_URL,
    auth_configured: hasAuth,
    data_available: dataAvailable,
    ping: {
      ok: ping.ok,
      status: ping.status,
      latency_ms: ping.latency_ms,
      ...(ping.error ? { error: ping.error } : {}),
    },
    crm: {
      leads: leadCount,
      deals: dealCount,
      quotations: quotationCount,
      data_available: dataAvailable,
    },
    site: "tower.saillant.cc",
    note: "Frappe CRM + ERPNext v15 — Electron Rare backoffice",
  });
});

export { frappeRoutes };

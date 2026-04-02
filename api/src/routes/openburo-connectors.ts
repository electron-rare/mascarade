/**
 * Open Buro — Connectors (Phase 2)
 * Bridges between apps and the CloudEvents event bus
 */

import { Hono } from "hono";

const connectors = new Hono();

// ============================================================================
// GRIST WEBHOOK RECEIVER
// Grist sends webhooks on row changes. We normalize to CloudEvents.
// Setup in Grist: Settings → Webhooks → URL: https://api.saillant.cc/openburo/connectors/grist/webhook
// ============================================================================

connectors.post("/grist/webhook", async (c) => {
  const payload = await c.req.json();

  // Grist webhook payload format: array of records
  const records = Array.isArray(payload) ? payload : [payload];
  const events: any[] = [];

  for (const record of records) {
    const eventType = record.id && !record._deleted
      ? (record._isNew ? "row.created" : "row.updated")
      : "row.deleted";

    events.push({
      type: `grist.${eventType}`,
      source: "/openburo/apps/grist",
      subject: `${record.tableId || "unknown"}/${record.id || "?"}`,
      data: {
        table: record.tableId,
        row_id: record.id,
        fields: record.fields || record,
        doc_id: c.req.query("doc") || "unknown",
      },
    });
  }

  // Publish to event bus
  const published: string[] = [];
  for (const event of events) {
    try {
      const res = await fetch("http://localhost:3100/openburo/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(event),
      });
      const result = await res.json() as any;
      published.push(result.id);
    } catch (err: any) {
      console.error("[connector/grist]", err.message);
    }
  }

  return c.json({ received: records.length, published: published.length, ids: published });
});

// ============================================================================
// DOLIBARR WEBHOOK RECEIVER
// Dolibarr triggers module sends webhooks on entity changes.
// Setup: Dolibarr → Modules → Triggers → Webhook URL
// ============================================================================

connectors.post("/dolibarr/webhook", async (c) => {
  const payload = await c.req.json();

  // Dolibarr webhook payload varies by trigger type
  const triggerCode = payload.triggername || payload.action || "unknown";
  const objectType = payload.object?.element || payload.element || "unknown";
  const objectId = payload.object?.id || payload.id || "?";

  // Map Dolibarr trigger codes to CloudEvents types
  const typeMap: Record<string, string> = {
    "COMPANY_CREATE": "contact.created",
    "COMPANY_MODIFY": "contact.updated",
    "COMPANY_DELETE": "contact.deleted",
    "CONTACT_CREATE": "contact.created",
    "CONTACT_MODIFY": "contact.updated",
    "BILL_CREATE": "invoice.created",
    "BILL_VALIDATE": "invoice.sent",
    "BILL_PAYED": "invoice.paid",
    "BILL_DELETE": "invoice.deleted",
    "PROPAL_CREATE": "quote.created",
    "PROPAL_VALIDATE": "quote.sent",
    "PROPAL_CLOSE_SIGNED": "quote.accepted",
    "PROJECT_CREATE": "project.created",
    "PROJECT_MODIFY": "project.updated",
    "PROJECT_CLOSE": "project.closed",
    "TASK_CREATE": "task.created",
    "TASK_MODIFY": "task.updated",
  };

  const eventType = typeMap[triggerCode] || `dolibarr.${triggerCode.toLowerCase()}`;

  const event = {
    type: eventType,
    source: "/openburo/apps/dolibarr",
    subject: `${objectType}/${objectId}`,
    data: {
      trigger: triggerCode,
      element: objectType,
      element_id: objectId,
      user: payload.user?.login || "system",
      ...( payload.object ? {
        ref: payload.object.ref,
        label: payload.object.label || payload.object.name || payload.object.nom,
        email: payload.object.email,
        total_ttc: payload.object.total_ttc,
        status: payload.object.status || payload.object.statut,
      } : {}),
    },
  };

  try {
    const res = await fetch("http://localhost:3100/openburo/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    });
    const result = await res.json() as any;
    return c.json({ received: true, event_id: result.id, type: eventType });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

// ============================================================================
// N8N WEBHOOK RECEIVER (generic)
// N8N workflows can POST events here for any app
// ============================================================================

connectors.post("/n8n/webhook", async (c) => {
  const payload = await c.req.json();

  if (!payload.type || !payload.source) {
    return c.json({ error: "Missing required fields: type, source" }, 400);
  }

  try {
    const res = await fetch("http://localhost:3100/openburo/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await res.json() as any;
    return c.json({ received: true, event_id: result.id });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

// ============================================================================
// STATUS — which connectors are configured
// ============================================================================

connectors.get("/status", (c) => {
  return c.json({
    connectors: [
      {
        id: "grist",
        app: "grist",
        type: "webhook",
        endpoint: "/openburo/connectors/grist/webhook",
        status: "active",
        setup: "Grist → Settings → Webhooks → add URL",
      },
      {
        id: "dolibarr",
        app: "dolibarr",
        type: "webhook",
        endpoint: "/openburo/connectors/dolibarr/webhook",
        status: "active",
        setup: "Dolibarr → Setup → Modules → Enable API + Triggers",
      },
      {
        id: "n8n",
        app: "n8n",
        type: "webhook",
        endpoint: "/openburo/connectors/n8n/webhook",
        status: "active",
        setup: "N8N → Workflow → HTTP Request node → POST to endpoint",
      },
    ],
  });
});

export { connectors };

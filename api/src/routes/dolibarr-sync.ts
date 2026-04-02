import { Hono } from "hono";
import { resolveBusinessObjectFile } from "./openburo-files.js";

const dolibarrSync = new Hono();

function required(body: Record<string, unknown>, fields: string[]): string | null {
  for (const field of fields) {
    if (!body[field]) return field;
  }
  return null;
}

dolibarrSync.post("/customer", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const missing = required(body as Record<string, unknown>, ["entity_id", "client_ref"]);
  if (missing) return c.json({ error: `Missing required field: ${missing}` }, 400);

  return c.json({
    entity_type: "customer",
    entity_id: String(body.entity_id),
    nextcloud_path: `/clients/${String(body.client_ref).trim()}/`,
    sync_status: "planned",
    source_app: "dolibarr",
  });
});

dolibarrSync.post("/invoice", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const missing = required(body as Record<string, unknown>, ["entity_id", "client_ref", "invoice_ref"]);
  if (missing) return c.json({ error: `Missing required field: ${missing}` }, 400);

  return c.json(resolveBusinessObjectFile({
    type: "invoice",
    id: String(body.entity_id),
    client_ref: String(body.client_ref),
    invoice_ref: String(body.invoice_ref),
    nextcloud_path: body.nextcloud_path ? String(body.nextcloud_path) : undefined,
    filename: body.filename ? String(body.filename) : `${String(body.invoice_ref)}.pdf`,
    mime_type: body.mime_type ? String(body.mime_type) : "application/pdf",
    source_app: "dolibarr",
  }));
});

dolibarrSync.post("/proposal", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const missing = required(body as Record<string, unknown>, ["entity_id", "client_ref", "proposal_ref"]);
  if (missing) return c.json({ error: `Missing required field: ${missing}` }, 400);

  return c.json(resolveBusinessObjectFile({
    type: "proposal",
    id: String(body.entity_id),
    client_ref: String(body.client_ref),
    proposal_ref: String(body.proposal_ref),
    nextcloud_path: body.nextcloud_path ? String(body.nextcloud_path) : undefined,
    filename: body.filename ? String(body.filename) : `${String(body.proposal_ref)}.odt`,
    mime_type: body.mime_type ? String(body.mime_type) : "application/vnd.oasis.opendocument.text",
    source_app: "dolibarr",
  }));
});

export { dolibarrSync };

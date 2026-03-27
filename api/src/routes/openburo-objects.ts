import { Hono } from "hono";

const openburoObjects = new Hono();

// === Business Object Schemas (JSON Schema subset) ===

const SCHEMAS: Record<string, object> = {
  contact: {
    type: "contact",
    description: "Personne ou organisation — partagé entre CRM, ERP, annuaire",
    properties: {
      id: { type: "string", description: "ID unique (source_app:local_id)" },
      name: { type: "string" },
      email: { type: "string", format: "email" },
      phone: { type: "string" },
      organization: { type: "string" },
      role: { type: "string" },
      source_app: { type: "string", description: "App d'origine (dolibarr, people, grist)" },
      source_id: { type: "string", description: "ID dans l'app d'origine" },
      tags: { type: "array", items: { type: "string" } },
      created_at: { type: "string", format: "date-time" },
      updated_at: { type: "string", format: "date-time" },
    },
    required: ["id", "name", "source_app"],
  },
  document: {
    type: "document",
    description: "Document partagé — fichier, note, page wiki",
    properties: {
      id: { type: "string" },
      title: { type: "string" },
      url: { type: "string", format: "uri" },
      mime_type: { type: "string" },
      size_bytes: { type: "number" },
      author: { type: "string" },
      source_app: { type: "string", description: "App d'origine (docs, drive, docuseal)" },
      source_id: { type: "string" },
      tags: { type: "array", items: { type: "string" } },
      created_at: { type: "string", format: "date-time" },
      updated_at: { type: "string", format: "date-time" },
    },
    required: ["id", "title", "source_app"],
  },
  task: {
    type: "task",
    description: "Tâche ou action — projet, TODO, ticket",
    properties: {
      id: { type: "string" },
      title: { type: "string" },
      description: { type: "string" },
      status: { type: "string", enum: ["todo", "in_progress", "done", "cancelled"] },
      priority: { type: "string", enum: ["low", "medium", "high", "critical"] },
      assignee: { type: "string" },
      due_date: { type: "string", format: "date" },
      project: { type: "string" },
      source_app: { type: "string", description: "App d'origine (grist, dolibarr, n8n)" },
      source_id: { type: "string" },
      tags: { type: "array", items: { type: "string" } },
      created_at: { type: "string", format: "date-time" },
      updated_at: { type: "string", format: "date-time" },
    },
    required: ["id", "title", "status", "source_app"],
  },
  invoice: {
    type: "invoice",
    description: "Facture ou devis — facturation FR",
    properties: {
      id: { type: "string" },
      number: { type: "string", description: "Numéro de facture (ex: FA2026-001)" },
      type: { type: "string", enum: ["invoice", "quote", "credit_note"] },
      status: { type: "string", enum: ["draft", "sent", "paid", "overdue", "cancelled"] },
      amount_ht: { type: "number", description: "Montant HT en euros" },
      amount_ttc: { type: "number", description: "Montant TTC en euros" },
      vat_rate: { type: "number", description: "Taux TVA (ex: 20)" },
      currency: { type: "string", default: "EUR" },
      client_id: { type: "string", description: "Référence contact client" },
      client_name: { type: "string" },
      issue_date: { type: "string", format: "date" },
      due_date: { type: "string", format: "date" },
      paid_date: { type: "string", format: "date" },
      source_app: { type: "string", description: "App d'origine (dolibarr)" },
      source_id: { type: "string" },
      pdf_url: { type: "string", format: "uri" },
    },
    required: ["id", "number", "type", "status", "amount_ttc", "source_app"],
  },
  event: {
    type: "event",
    description: "Événement calendrier — réunion, formation, deadline",
    properties: {
      id: { type: "string" },
      title: { type: "string" },
      description: { type: "string" },
      start: { type: "string", format: "date-time" },
      end: { type: "string", format: "date-time" },
      location: { type: "string" },
      attendees: { type: "array", items: { type: "string" } },
      source_app: { type: "string", description: "App d'origine (calendars, meet)" },
      source_id: { type: "string" },
    },
    required: ["id", "title", "start", "source_app"],
  },
};

// GET /openburo/objects/schemas — list all business object types
openburoObjects.get("/schemas", (c) => {
  const types = Object.keys(SCHEMAS).map((k) => ({
    type: k,
    description: (SCHEMAS[k] as any).description,
    required: (SCHEMAS[k] as any).required,
    property_count: Object.keys((SCHEMAS[k] as any).properties).length,
  }));
  return c.json({ schemas: types, count: types.length });
});

// GET /openburo/objects/schemas/:type — get full schema for a type
openburoObjects.get("/schemas/:type", (c) => {
  const type = c.req.param("type");
  const schema = SCHEMAS[type];
  if (!schema) return c.json({ error: `Unknown object type: ${type}` }, 404);
  return c.json(schema);
});

// === Phase 2: Live connectors Dolibarr + Grist ===

const DOLIBARR_URL = process.env.DOLIBARR_URL || "https://erp.saillant.cc";
const DOLIBARR_KEY = process.env.DOLIBARR_API_KEY || "";
const GRIST_URL = process.env.GRIST_URL || "https://grist.saillant.cc";
const GRIST_KEY = process.env.GRIST_API_KEY || "";

async function dolibarrGet(endpoint: string) {
  const res = await fetch(`${DOLIBARR_URL}/api/index.php${endpoint}`, {
    headers: { DOLAPIKEY: DOLIBARR_KEY },
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`Dolibarr ${res.status}`);
  return res.json();
}

async function gristGet(endpoint: string) {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (GRIST_KEY) headers.Authorization = `Bearer ${GRIST_KEY}`;
  const res = await fetch(`${GRIST_URL}${endpoint}`, {
    headers,
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`Grist ${res.status}`);
  return res.json();
}

const PROPOSAL_STATUS: Record<number, string> = { 0: "draft", 1: "sent", 2: "paid", 3: "cancelled", 4: "paid" };
const INVOICE_STATUS: Record<number, string> = { 0: "draft", 1: "sent", 2: "sent", 3: "cancelled", 5: "sent", 6: "paid" };

// GET /openburo/objects/contact — Dolibarr thirdparties
openburoObjects.get("/contact", async (c) => {
  try {
    const data = await dolibarrGet("/thirdparties?sortfield=t.nom&sortorder=ASC&limit=100");
    const objects = (Array.isArray(data) ? data : []).map((tp: any) => ({
      id: `dolibarr:${tp.id}`,
      name: tp.name || tp.nom,
      email: tp.email || "",
      phone: tp.phone || "",
      organization: tp.name_alias || "",
      source_app: "dolibarr",
      source_id: String(tp.id),
      tags: [tp.client >= 1 ? "client" : null, tp.fournisseur ? "fournisseur" : null].filter(Boolean),
    }));
    return c.json({ type: "contact", objects, count: objects.length });
  } catch (e) {
    return c.json({ type: "contact", objects: [], count: 0, error: (e as Error).message }, 502);
  }
});

// GET /openburo/objects/invoice — Dolibarr invoices + proposals
openburoObjects.get("/invoice", async (c) => {
  const subtype = c.req.query("type"); // "invoice" | "quote"
  try {
    const objects: any[] = [];
    if (!subtype || subtype === "quote") {
      const proposals = await dolibarrGet("/proposals?sortfield=t.rowid&sortorder=DESC&limit=50");
      for (const p of Array.isArray(proposals) ? proposals : []) {
        objects.push({
          id: `dolibarr:proposal:${p.id}`,
          number: p.ref,
          type: "quote",
          status: PROPOSAL_STATUS[p.statut as number] || "draft",
          amount_ht: Number(p.total_ht) || 0,
          amount_ttc: Number(p.total_ttc) || 0,
          currency: "EUR",
          client_name: p.nom_thirdparty || "",
          client_id: `dolibarr:${p.socid}`,
          issue_date: p.date ? new Date(p.date * 1000).toISOString().slice(0, 10) : null,
          source_app: "dolibarr",
          source_id: String(p.id),
        });
      }
    }
    if (!subtype || subtype === "invoice") {
      const invoices = await dolibarrGet("/invoices?sortfield=t.rowid&sortorder=DESC&limit=50");
      for (const inv of Array.isArray(invoices) ? invoices : []) {
        objects.push({
          id: `dolibarr:invoice:${inv.id}`,
          number: inv.ref,
          type: "invoice",
          status: inv.paye ? "paid" : (INVOICE_STATUS[inv.statut as number] || "draft"),
          amount_ht: Number(inv.total_ht) || 0,
          amount_ttc: Number(inv.total_ttc) || 0,
          currency: "EUR",
          client_name: inv.nom_thirdparty || "",
          client_id: `dolibarr:${inv.socid}`,
          issue_date: inv.date ? new Date(inv.date * 1000).toISOString().slice(0, 10) : null,
          due_date: inv.date_lim_reglement ? new Date(inv.date_lim_reglement * 1000).toISOString().slice(0, 10) : null,
          source_app: "dolibarr",
          source_id: String(inv.id),
        });
      }
    }
    return c.json({ type: "invoice", objects, count: objects.length });
  } catch (e) {
    return c.json({ type: "invoice", objects: [], count: 0, error: (e as Error).message }, 502);
  }
});

// GET /openburo/objects/task — Dolibarr tasks
openburoObjects.get("/task", async (c) => {
  try {
    const data = await dolibarrGet("/tasks?sortfield=t.datec&sortorder=DESC&limit=50");
    const objects = (Array.isArray(data) ? data : []).map((t: any) => ({
      id: `dolibarr:${t.id}`,
      title: t.label || t.ref,
      description: t.description || "",
      status: Number(t.progress) >= 100 ? "done" : Number(t.progress) > 0 ? "in_progress" : "todo",
      priority: "medium",
      project: t.fk_project ? `dolibarr:project:${t.fk_project}` : undefined,
      due_date: t.date_end ? new Date(t.date_end * 1000).toISOString().slice(0, 10) : undefined,
      source_app: "dolibarr",
      source_id: String(t.id),
    }));
    return c.json({ type: "task", objects, count: objects.length });
  } catch (e) {
    return c.json({ type: "task", objects: [], count: 0, error: (e as Error).message }, 502);
  }
});

// GET /openburo/objects/document — Grist documents
openburoObjects.get("/document", async (c) => {
  try {
    const data = await gristGet("/api/docs");
    const objects = (Array.isArray(data) ? data : []).map((d: any) => ({
      id: `grist:${d.id}`,
      title: d.name,
      url: `${GRIST_URL}/doc/${d.id}`,
      mime_type: "application/vnd.grist",
      source_app: "grist",
      source_id: String(d.id),
      created_at: d.createdAt,
      updated_at: d.updatedAt,
    }));
    return c.json({ type: "document", objects, count: objects.length });
  } catch (e) {
    return c.json({ type: "document", objects: [], count: 0, error: (e as Error).message }, 502);
  }
});

// GET /openburo/objects/event — placeholder (calendars API)
openburoObjects.get("/event", (c) => {
  return c.json({ type: "event", objects: [], count: 0, message: "Suite Calendars connector coming soon" });
});

// Fallback for unknown types
openburoObjects.get("/:type", (c) => {
  const type = c.req.param("type");
  if (!SCHEMAS[type]) return c.json({ error: `Unknown object type: ${type}` }, 404);
  return c.json({ type, objects: [], count: 0 });
});

export { openburoObjects, SCHEMAS as BUSINESS_OBJECT_SCHEMAS };

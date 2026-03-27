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

// GET /openburo/objects/:type — search objects across apps (placeholder)
openburoObjects.get("/:type", (c) => {
  const type = c.req.param("type");
  if (!SCHEMAS[type]) return c.json({ error: `Unknown object type: ${type}` }, 404);

  // TODO Phase 2: query Dolibarr API, Grist API, etc. and normalize to schema
  return c.json({
    type,
    objects: [],
    count: 0,
    message: "Cross-app object search will be available in Phase 2 (connectors Dolibarr + Grist)",
  });
});

export { openburoObjects, SCHEMAS as BUSINESS_OBJECT_SCHEMAS };

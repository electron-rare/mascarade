import { Hono } from "hono";
import { z } from "zod";

// =============================================================================
// Open Buro — EU interoperability standard for sovereign collaborative suites
// https://openburo.eu/
// =============================================================================

const openburoApp = new Hono();

// --- App Manifest Schema ---
const AppManifestSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().optional(),
  url: z.string().url(),
  icon: z.string().optional(),
  version: z.string().optional(),
  auth: z.object({
    type: z.enum(["oidc", "forward-auth", "none"]),
    client_id: z.string().optional(),
    issuer: z.string().optional(),
  }),
  capabilities: z.array(z.string()),
  events: z.object({
    publish: z.array(z.string()).default([]),
    subscribe: z.array(z.string()).default([]),
  }).optional(),
  api: z.object({
    openapi: z.string().optional(),
    graphql: z.string().optional(),
    rest: z.string().optional(),
  }).optional(),
  health: z.string().optional(),
  node: z.string().optional(),
});

type AppManifest = z.infer<typeof AppManifestSchema>;

// --- App Registry (static for now, later from DB) ---
const APP_REGISTRY: AppManifest[] = [
  {
    id: "conversations",
    name: "Conversations",
    description: "Chatbot IA collaboratif",
    url: "https://conversations.saillant.cc",
    auth: { type: "forward-auth", client_id: "conversations", issuer: "https://auth.saillant.cc/realms/electron_rare" },
    capabilities: ["chat", "ai"],
    events: { publish: ["message.sent"], subscribe: [] },
    health: "http://192.168.0.120:8082/",
    node: "tower",
  },
  {
    id: "docs",
    name: "Docs / Impress",
    description: "Éditeur collaboratif",
    url: "https://docs.saillant.cc",
    auth: { type: "forward-auth", client_id: "impress", issuer: "https://auth.saillant.cc/realms/electron_rare" },
    capabilities: ["documents", "collaboration"],
    events: { publish: ["document.created", "document.updated"], subscribe: [] },
    health: "http://192.168.0.120:8073/",
    node: "tower",
  },
  {
    id: "meet",
    name: "Meet",
    description: "Visioconférence",
    url: "https://meet.saillant.cc",
    auth: { type: "forward-auth", client_id: "meet", issuer: "https://auth.saillant.cc/realms/electron_rare" },
    capabilities: ["video", "audio", "transcription"],
    events: { publish: ["meeting.started", "meeting.ended"], subscribe: [] },
    health: "http://192.168.0.120:8084/",
    node: "tower",
  },
  {
    id: "drive",
    name: "Drive",
    description: "Fichiers collaboratifs",
    url: "https://drive.saillant.cc",
    auth: { type: "forward-auth" },
    capabilities: ["files", "sharing"],
    health: "http://192.168.0.120:8086/",
    node: "tower",
  },
  {
    id: "people",
    name: "People",
    description: "Annuaire",
    url: "https://people.saillant.cc",
    auth: { type: "forward-auth" },
    capabilities: ["contacts", "teams"],
    health: "http://192.168.0.120:8087/",
    node: "tower",
  },
  {
    id: "messages",
    name: "Messages",
    description: "Inbox",
    url: "https://messages.saillant.cc",
    auth: { type: "forward-auth" },
    capabilities: ["email", "inbox"],
    health: "http://192.168.0.120:8090/",
    node: "tower",
  },
  {
    id: "calendars",
    name: "Calendars",
    description: "Agenda collaboratif",
    url: "https://calendars.saillant.cc",
    auth: { type: "forward-auth" },
    capabilities: ["calendar", "scheduling"],
    health: "http://192.168.0.120:8089/",
    node: "tower",
  },
  {
    id: "grist",
    name: "Grist",
    description: "Tableur collaboratif / base de données",
    url: "https://grist.saillant.cc",
    auth: { type: "oidc", client_id: "grist", issuer: "https://auth.saillant.cc/realms/electron_rare" },
    capabilities: ["spreadsheet", "database", "formulas", "api"],
    events: { publish: ["row.created", "row.updated", "row.deleted"], subscribe: [] },
    api: { rest: "https://grist.saillant.cc/api" },
    health: "http://192.168.0.120:8484/",
    node: "tower",
  },
  {
    id: "dolibarr",
    name: "Dolibarr",
    description: "ERP / Facturation FR",
    url: "https://erp.saillant.cc",
    auth: { type: "forward-auth", client_id: "dolibarr", issuer: "https://auth.saillant.cc/realms/electron_rare" },
    capabilities: ["invoices", "contacts", "projects", "crm"],
    events: { publish: ["contact.created", "invoice.sent", "project.updated"], subscribe: ["contact.updated"] },
    api: { rest: "https://erp.saillant.cc/api/index.php" },
    health: "http://192.168.0.120:8488/",
    node: "tower",
  },
  {
    id: "docuseal",
    name: "DocuSeal",
    description: "Signature électronique",
    url: "https://signature.saillant.cc",
    auth: { type: "forward-auth" },
    capabilities: ["signatures", "documents"],
    events: { publish: ["document.signed"], subscribe: [] },
    health: "http://192.168.0.120:7070/",
    node: "tower",
  },
  {
    id: "garage",
    name: "Garage S3",
    description: "Stockage objet souverain",
    url: "https://s3.saillant.cc",
    auth: { type: "none" },
    capabilities: ["storage", "s3"],
    api: { rest: "https://s3.saillant.cc" },
    health: "http://192.168.0.120:3900/",
    node: "tower",
  },
  {
    id: "matrix",
    name: "Matrix / Element",
    description: "Messagerie instantanée chiffrée",
    url: "https://chat.saillant.cc",
    auth: { type: "oidc", client_id: "synapse", issuer: "https://auth.saillant.cc/realms/electron_rare" },
    capabilities: ["messaging", "encryption", "federation"],
    api: { rest: "https://matrix.saillant.cc/_matrix/client/v3" },
    health: "http://192.168.0.119:8008/_matrix/client/versions",
    node: "photon",
  },
  {
    id: "transfert",
    name: "Transfert",
    description: "Envoi de fichiers",
    url: "https://transfert.saillant.cc",
    auth: { type: "forward-auth" },
    capabilities: ["file-transfer"],
    health: "http://pingvin-share:3000/",
    node: "photon",
  },
  {
    id: "mascarade",
    name: "Mascarade",
    description: "Orchestrateur IA agentique",
    url: "https://api.saillant.cc",
    auth: { type: "none" },
    capabilities: ["ai", "orchestration", "rag", "agents", "knowledge-graph"],
    events: { publish: ["agent.completed", "rag.query"], subscribe: ["*"] },
    api: { rest: "https://api.saillant.cc/v1/api" },
    health: "http://192.168.0.120:3100/health",
    node: "tower",
  },
];

// --- Routes ---

// GET /openburo/apps — list all registered apps
openburoApp.get("/apps", (c) => {
  const capability = c.req.query("capability");
  const node = c.req.query("node");
  let apps = APP_REGISTRY;
  if (capability) {
    apps = apps.filter((a) => a.capabilities.includes(capability));
  }
  if (node) {
    apps = apps.filter((a) => a.node === node);
  }
  return c.json({ apps, count: apps.length });
});

// GET /openburo/apps/:id — get app details
openburoApp.get("/apps/:id", (c) => {
  const app_entry = APP_REGISTRY.find((a) => a.id === c.req.param("id"));
  if (!app_entry) return c.json({ error: "App not found" }, 404);
  return c.json(app_entry);
});

// GET /openburo/capabilities — list all unique capabilities
openburoApp.get("/capabilities", (c) => {
  const caps = [...new Set(APP_REGISTRY.flatMap((a) => a.capabilities))].sort();
  return c.json({ capabilities: caps });
});

// GET /openburo/health — health status of all apps
openburoApp.get("/health", async (c) => {
  const results = await Promise.allSettled(
    APP_REGISTRY.filter((a) => a.health).map(async (a) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      try {
        const res = await fetch(a.health!, { signal: controller.signal });
        return { id: a.id, name: a.name, status: res.ok ? "up" : "down", code: res.status };
      } catch {
        return { id: a.id, name: a.name, status: "down", code: 0 };
      } finally {
        clearTimeout(timeout);
      }
    })
  );
  const statuses = results.map((r) => (r.status === "fulfilled" ? r.value : { id: "?", name: "?", status: "error", code: 0 }));
  const up = statuses.filter((s) => s.status === "up").length;
  return c.json({ total: statuses.length, up, down: statuses.length - up, services: statuses });
});

export { openburoApp as openburo, APP_REGISTRY };

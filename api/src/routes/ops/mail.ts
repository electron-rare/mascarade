import { Hono } from "hono";

const mailRoutes = new Hono();

let cachedCampaigns: unknown[] = [];
let cachedSubscribers: { total: number; active: number | null } = { total: 0, active: null };
let lastMailFetch = 0;
let lastMailAttempt = 0;
let lastMailError: string | null = null;
let lastMailUpstreamStatus: number | null = null;
const CACHE_TTL = 5 * 60 * 1000;

const LISTMONK_URL = process.env.LISTMONK_URL || "https://mail.saillant.cc";
const LISTMONK_USER = process.env.LISTMONK_USER || "";
const LISTMONK_PASS = process.env.LISTMONK_PASS || "";

type MailResponsePayload = {
  ok: boolean;
  stale: boolean;
  campaigns: unknown[];
  subscribers: { total: number; active: number | null };
  lastFetch: number;
  lastAttempt: number;
  auth_configured: boolean;
  error?: string;
  upstream_status?: number;
};

function buildMailPayload(): MailResponsePayload {
  const stale = lastMailFetch === 0 || Date.now() - lastMailFetch > CACHE_TTL;
  return {
    ok: lastMailError === null,
    stale,
    campaigns: cachedCampaigns,
    subscribers: cachedSubscribers,
    lastFetch: lastMailFetch,
    lastAttempt: lastMailAttempt,
    auth_configured: Boolean(LISTMONK_USER && LISTMONK_PASS),
    ...(lastMailError ? { error: lastMailError } : {}),
    ...(lastMailUpstreamStatus !== null ? { upstream_status: lastMailUpstreamStatus } : {}),
  };
}

async function refreshMail(): Promise<boolean> {
  lastMailAttempt = Date.now();
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (LISTMONK_USER && LISTMONK_PASS) {
      headers["Authorization"] = "Basic " + Buffer.from(`${LISTMONK_USER}:${LISTMONK_PASS}`).toString("base64");
    }

    const [campRes, subRes] = await Promise.allSettled([
      fetch(`${LISTMONK_URL}/api/campaigns?order_by=created_at&order=desc&per_page=50`, { headers }),
      fetch(`${LISTMONK_URL}/api/subscribers?per_page=1`, { headers }),
    ]);

    if (campRes.status === "fulfilled" && campRes.value.ok) {
      lastMailUpstreamStatus = campRes.value.status;
      const d = await campRes.value.json();
      cachedCampaigns = d.data?.results || [];
    }

    if (subRes.status === "fulfilled" && subRes.value.ok) {
      lastMailUpstreamStatus = subRes.value.status;
      const d = await subRes.value.json();
      cachedSubscribers = { total: d.data?.total || 0, active: d.data?.active ?? null };
    }

    if (
      campRes.status === "fulfilled" &&
      !campRes.value.ok &&
      lastMailUpstreamStatus === null
    ) {
      lastMailUpstreamStatus = campRes.value.status;
    }
    if (
      subRes.status === "fulfilled" &&
      !subRes.value.ok &&
      lastMailUpstreamStatus === null
    ) {
      lastMailUpstreamStatus = subRes.value.status;
    }

    const hadSuccess =
      (campRes.status === "fulfilled" && campRes.value.ok) ||
      (subRes.status === "fulfilled" && subRes.value.ok);
    if (!hadSuccess) {
      throw new Error("Listmonk refresh failed");
    }

    lastMailFetch = Date.now();
    lastMailError = null;
    return true;
  } catch (e) {
    lastMailError = e instanceof Error ? e.message : String(e);
    console.warn("[ops/mail] refresh failed:", lastMailError);
    return false;
  }
}

setInterval(refreshMail, CACHE_TTL);
refreshMail();

mailRoutes.get("/mail", async (c) => {
  if (Date.now() - lastMailFetch > CACHE_TTL) {
    await refreshMail();
  }
  const payload = buildMailPayload();
  const status = !payload.ok && lastMailFetch === 0 ? 503 : 200;
  return c.json(payload, status);
});

mailRoutes.get("/mail/stats", async (c) => {
  if (Date.now() - lastMailFetch > CACHE_TTL) {
    await refreshMail();
  }
  const payload = buildMailPayload();
  const status = !payload.ok && lastMailFetch === 0 ? 503 : 200;
  return c.json({
    ok: payload.ok,
    stale: payload.stale,
    totalCampaigns: cachedCampaigns.length,
    subscribers: cachedSubscribers,
    lastFetch: lastMailFetch,
    lastAttempt: lastMailAttempt,
    auth_configured: payload.auth_configured,
    ...(payload.error ? { error: payload.error } : {}),
    ...(payload.upstream_status !== undefined ? { upstream_status: payload.upstream_status } : {}),
  }, status);
});

export { mailRoutes };

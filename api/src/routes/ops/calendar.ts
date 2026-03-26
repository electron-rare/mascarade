import { Hono } from "hono";

const calendarRoutes = new Hono();

// In-memory cache
let cachedEvents: unknown[] = [];
let lastFetch = 0;
let lastAttempt = 0;
let lastError: string | null = null;
let lastUpstreamStatus: number | null = null;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

const CALCOM_URL = process.env.CALCOM_URL || "http://localhost:3800";
const CALCOM_API_KEY = process.env.CALCOM_API_KEY || "";

type CalendarResponsePayload = {
  ok: boolean;
  stale: boolean;
  events: unknown[];
  lastFetch: number;
  lastAttempt: number;
  source: "calcom";
  auth_configured: boolean;
  error?: string;
  upstream_status?: number;
};

function buildCalendarPayload(events: unknown[]): CalendarResponsePayload {
  const stale = lastFetch === 0 || Date.now() - lastFetch > CACHE_TTL;
  return {
    ok: lastError === null,
    stale,
    events,
    lastFetch,
    lastAttempt,
    source: "calcom",
    auth_configured: CALCOM_API_KEY.length > 0,
    ...(lastError ? { error: lastError } : {}),
    ...(lastUpstreamStatus !== null ? { upstream_status: lastUpstreamStatus } : {}),
  };
}

async function refreshCalendar(): Promise<boolean> {
  lastAttempt = Date.now();
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (CALCOM_API_KEY) headers["Authorization"] = `Bearer ${CALCOM_API_KEY}`;

    const res = await fetch(`${CALCOM_URL}/api/bookings`, { headers });
    lastUpstreamStatus = res.status;
    if (!res.ok) throw new Error(`Cal.com ${res.status}`);
    const data = await res.json();
    cachedEvents = Array.isArray(data.bookings) ? data.bookings : (Array.isArray(data) ? data : []);
    lastFetch = Date.now();
    lastError = null;
    return true;
  } catch (e) {
    lastError = e instanceof Error ? e.message : String(e);
    console.warn("[ops/calendar] refresh failed:", lastError);
    return false;
  }
}

// Auto-refresh every 5 minutes
setInterval(refreshCalendar, CACHE_TTL);
refreshCalendar();

calendarRoutes.get("/calendar", async (c) => {
  if (Date.now() - lastFetch > CACHE_TTL) {
    await refreshCalendar();
  }
  const payload = buildCalendarPayload(cachedEvents);
  const status = !payload.ok && lastFetch === 0 ? 503 : 200;
  return c.json(payload, status);
});

calendarRoutes.get("/calendar/upcoming", async (c) => {
  if (Date.now() - lastFetch > CACHE_TTL) {
    await refreshCalendar();
  }
  const now = new Date().toISOString();
  const upcoming = cachedEvents.filter((e: any) => e.startTime > now || e.start > now);
  const payload = buildCalendarPayload(upcoming);
  const status = !payload.ok && lastFetch === 0 ? 503 : 200;
  return c.json({ ...payload, count: upcoming.length }, status);
});

export { calendarRoutes };

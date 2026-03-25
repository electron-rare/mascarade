const API_KEY_PERSIST_FLAG = "mascarade_key_persist";
const DEFAULT_TIMEOUT_MS = 30_000;
const VALIDATE_TIMEOUT_MS = 5_000;
const AUTH_SESSION_PATH = "/api/auth/session";

async function upsertSessionCookie(key: string, persist: boolean): Promise<boolean> {
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  try {
    const res = await fetch(AUTH_SESSION_PATH, {
      method: "POST",
      headers,
      body: JSON.stringify({ api_key: key, persist }),
      credentials: "include",
      signal: AbortSignal.timeout(VALIDATE_TIMEOUT_MS),
    });
    return res.ok;
  } catch {
    return false;
  }
}

// --- Global 401 bus ---
type Auth401Handler = () => void;
const _auth401Listeners = new Set<Auth401Handler>();

export function onAuth401(handler: Auth401Handler): () => void {
  _auth401Listeners.add(handler);
  return () => { _auth401Listeners.delete(handler); };
}

function _emit401() {
  for (const h of _auth401Listeners) {
    try { h(); } catch { /* swallow */ }
  }
}

export function getApiKey(): string {
  return "";
}

export function isPersisted(): boolean {
  try {
    return localStorage.getItem(API_KEY_PERSIST_FLAG) === "1";
  } catch {
    return false;
  }
}

export async function setApiKey(key: string, persist = false): Promise<boolean> {
  if (!key) {
    await clearApiKey();
    return false;
  }
  const ok = await upsertSessionCookie(key, persist);
  if (!ok) {
    await clearApiKey();
    return false;
  }
  try {
    localStorage.setItem(API_KEY_PERSIST_FLAG, persist ? "1" : "0");
  } catch { /* private browsing */ }
  return true;
}

export async function clearApiKey(): Promise<void> {
  try {
    await fetch(AUTH_SESSION_PATH, {
      method: "DELETE",
      credentials: "include",
      signal: AbortSignal.timeout(VALIDATE_TIMEOUT_MS),
    });
  } catch { /* ignore */ }
  try {
    localStorage.removeItem(API_KEY_PERSIST_FLAG);
  } catch { /* private browsing */ }
}

export async function validateApiKey(key?: string): Promise<boolean> {
  const candidate = (key || "").trim();
  if (candidate) {
    return upsertSessionCookie(candidate, isPersisted());
  }
  try {
    const res = await fetch("/api/agents/providers", {
      credentials: "include",
      signal: AbortSignal.timeout(VALIDATE_TIMEOUT_MS),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export type ApiOptions = RequestInit & {
  timeoutMs?: number;
};

function getBodyError(body: unknown): string | null {
  if (typeof body === "string" && body.trim()) {
    return body.trim();
  }

  if (body && typeof body === "object") {
    if ("error" in body && typeof body.error === "string" && body.error.trim()) {
      return body.error.trim();
    }

    if ("message" in body && typeof body.message === "string" && body.message.trim()) {
      return body.message.trim();
    }
  }

  return null;
}

function toAbortError(message: string): DOMException {
  return new DOMException(message, "AbortError");
}

function linkAbortSignal(
  controller: AbortController,
  signal?: AbortSignal | null,
): () => void {
  if (!signal) {
    return () => {};
  }

  if (signal.aborted) {
    controller.abort(signal.reason);
    return () => {};
  }

  const abort = () => controller.abort(signal.reason);
  signal.addEventListener("abort", abort, { once: true });
  return () => signal.removeEventListener("abort", abort);
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Session gateway expiree ou invalide. Reconnectez-vous.";
    }
    return error.message;
  }

  if (error instanceof Error && error.name === "AbortError") {
    return "Request cancelled";
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }

  return "Request failed";
}

export async function api<T>(
  path: string,
  options: ApiOptions = {},
): Promise<T> {
  const {
    headers: initHeaders,
    signal,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    ...requestOptions
  } = options;
  const headers = new Headers(initHeaders);
  if (requestOptions.body !== undefined && requestOptions.body !== null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const controller = new AbortController();
  const unlinkAbortSignal = linkAbortSignal(controller, signal);
  const timeout =
    timeoutMs > 0
      ? window.setTimeout(
          () => controller.abort(toAbortError("Request timed out")),
          timeoutMs,
        )
      : null;

  try {
    const res = await fetch(path, {
      ...requestOptions,
      headers,
      signal: controller.signal,
      credentials: "include",
    });

    const contentType = res.headers.get("content-type") ?? "";
    if (!res.ok) {
      const body = contentType.includes("application/json")
        ? await res.json().catch(() => null)
        : await res.text().catch(() => null);
      if (res.status === 401) {
        _emit401();
      }
      throw new ApiError(
        res.status,
        getBodyError(body) ?? res.statusText ?? "Request failed",
      );
    }

    if (res.status === 204) {
      return undefined as T;
    }

    if (contentType.includes("application/json")) {
      return res.json() as Promise<T>;
    }

    return (await res.text()) as T;
  } catch (error) {
    if (controller.signal.aborted) {
      const reason = controller.signal.reason;
      if (reason instanceof Error) {
        throw reason;
      }

      if (typeof reason === "string" && reason.trim()) {
        throw toAbortError(reason.trim());
      }

      throw toAbortError("Request cancelled");
    }

    throw error;
  } finally {
    if (timeout !== null) {
      window.clearTimeout(timeout);
    }
    unlinkAbortSignal();
  }
}

export function get<T>(path: string, options: ApiOptions = {}) {
  return api<T>(path, options);
}

export function post<T>(path: string, body?: unknown, options: ApiOptions = {}) {
  return api<T>(path, {
    ...options,
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function put<T>(path: string, body?: unknown, options: ApiOptions = {}) {
  return api<T>(path, {
    ...options,
    method: "PUT",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function del<T>(path: string, options: ApiOptions = {}) {
  return api<T>(path, {
    ...options,
    method: "DELETE",
  });
}

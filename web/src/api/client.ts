const API_KEY_COOKIE = "mascarade_key";
const DEFAULT_TIMEOUT_MS = 30_000;

function setCookie(name: string, value: string) {
  // SameSite=Strict + Secure in production — mitigates XSS/CSRF
  const secure = location.protocol === "https:" ? ";Secure" : "";
  document.cookie = `${name}=${encodeURIComponent(value)};SameSite=Strict;Path=/${secure}`;
}

function getCookie(name: string): string {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}

export function getApiKey(): string {
  return getCookie(API_KEY_COOKIE);
}

export function setApiKey(key: string) {
  setCookie(API_KEY_COOKIE, key);
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
  const key = getApiKey();
  const headers = new Headers(initHeaders);
  if (requestOptions.body !== undefined && requestOptions.body !== null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (key && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${key}`);
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
    });

    const contentType = res.headers.get("content-type") ?? "";
    if (!res.ok) {
      const body = contentType.includes("application/json")
        ? await res.json().catch(() => null)
        : await res.text().catch(() => null);
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

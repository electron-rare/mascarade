const API_KEY_COOKIE = "mascarade_key";

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

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const key = getApiKey();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (key) headers["Authorization"] = `Bearer ${key}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30_000);

  const res = await fetch(path, {
    ...options,
    headers,
    signal: controller.signal,
  }).finally(() => clearTimeout(timeout));

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new ApiError(res.status, body.error || res.statusText);
  }

  return res.json();
}

export function get<T>(path: string) {
  return api<T>(path);
}

export function post<T>(path: string, body?: unknown) {
  return api<T>(path, {
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

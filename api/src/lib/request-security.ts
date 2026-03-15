type HeaderReadableRequest = {
  url: string;
  header(name: string): string | undefined;
};

function trustProxy(): boolean {
  return /^(1|true|yes)$/i.test(
    String(process.env.MASCARADE_TRUST_PROXY || process.env.RATE_LIMIT_TRUST_PROXY || "").trim(),
  );
}

function forwardedProto(headerValue: string | undefined): string {
  if (!headerValue) {
    return "";
  }
  const firstEntry = headerValue.split(",")[0]?.trim() || "";
  const match = /(?:^|;)proto=([^;]+)/i.exec(firstEntry);
  return match?.[1]?.trim().toLowerCase() || "";
}

function normalizedProto(headerValue: string | undefined): string {
  return String(headerValue || "").split(",")[0]?.trim().toLowerCase() || "";
}

export function isSecureRequest(req: HeaderReadableRequest): boolean {
  try {
    if (new URL(req.url).protocol === "https:") {
      return true;
    }
  } catch {
    return false;
  }

  if (!trustProxy()) {
    return false;
  }

  const proto =
    forwardedProto(req.header("forwarded")) ||
    normalizedProto(req.header("x-forwarded-proto")) ||
    normalizedProto(req.header("x-forwarded-protocol")) ||
    normalizedProto(req.header("x-forwarded-scheme"));

  if (proto) {
    return proto === "https";
  }

  return normalizedProto(req.header("x-forwarded-ssl")) === "on";
}

export function noStoreHeaders(): Record<string, string> {
  return {
    "Cache-Control": "no-store, max-age=0",
    Pragma: "no-cache",
  };
}

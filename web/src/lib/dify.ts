function isIpv4(hostname: string): boolean {
  return /^\d{1,3}(?:\.\d{1,3}){3}$/.test(hostname);
}

function baseHostname(hostname: string): string {
  return hostname.replace(/^www\./, "");
}

export function getDifyOrigin(): string {
  const { protocol, hostname } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1" || isIpv4(hostname)) {
    return `${protocol}//${hostname}:3500`;
  }
  return `${protocol}//dify.${baseHostname(hostname)}`;
}

export function getDifyHealthUrl(): string {
  const { protocol, hostname } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1" || isIpv4(hostname)) {
    return `${protocol}//${hostname}:5001/health`;
  }
  return `${window.location.origin}/dify-health`;
}

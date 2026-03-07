import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getApiKey, isPersisted, api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { getDifyHealthUrl } from "../../lib/dify";
import Button from "../ui/Button";

interface HealthData {
  status: string;
  auth_required?: boolean;
  core?: { status: string };
}

type TopBarProps = {
  eyebrow: string;
  title: string;
  description: string;
  section: string;
  index: string;
  navOpen: boolean;
  onMenuToggle: () => void;
};

function statusTone(ok: boolean) {
  return ok
    ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
    : "border-[#5d2332] bg-[#18070d]/80 text-error";
}

export default function TopBar({
  eyebrow,
  title,
  description,
  section,
  index,
  navOpen,
  onMenuToggle,
}: TopBarProps) {
  const { login, logout } = useAuth();
  const sessionTitleId = useId();
  const sessionPanelId = useId();
  const [open, setOpen] = useState(false);
  const [storedKey, setStoredKey] = useState(getApiKey);
  const [draftKey, setDraftKey] = useState(getApiKey);
  const [showKey, setShowKey] = useState(false);
  const [persist, setPersist] = useState(isPersisted);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [keyStatus, setKeyStatus] = useState<"idle" | "checking" | "valid" | "invalid">("idle");
  const [health, setHealth] = useState<HealthData | null>(null);
  const [clockLabel, setClockLabel] = useState(() =>
    new Intl.DateTimeFormat("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date()),
  );
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }

    window.requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    });
  }, [open]);

  useEffect(() => {
    const tick = () => {
      setClockLabel(
        new Intl.DateTimeFormat("fr-FR", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }).format(new Date()),
      );
    };

    const t = window.setInterval(tick, 1000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const fetchHealth = async () => {
      try {
        const res = await api<HealthData>("/health");
        if (mountedRef.current) setHealth(res);
      } catch {
        if (mountedRef.current) setHealth(null);
      }
    };
    fetchHealth();
    const t = window.setInterval(fetchHealth, 5000);
    return () => {
      mountedRef.current = false;
      window.clearInterval(t);
    };
  }, []);

  const save = async () => {
    const nextKey = draftKey.trim();
    if (!nextKey) {
      clear();
      return;
    }
    setKeyStatus("checking");
    const valid = await login(nextKey, persist);
    if (!valid) {
      setKeyStatus("invalid");
      return;
    }
    setStoredKey(nextKey);
    setDraftKey(nextKey);
    setKeyStatus("valid");
    setSavedAt(
      new Intl.DateTimeFormat("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date()),
    );
    setOpen(false);
  };

  const clear = () => {
    logout();
    setStoredKey("");
    setDraftKey("");
    setSavedAt(null);
    setKeyStatus("idle");
  };

  const apiOk = health?.status === "ok";
  const coreOk = health?.core?.status === "ok";
  const authReady = storedKey.trim().length > 0;
  const endpoints = useMemo(() => {
    const origin = window.location.origin;
    return {
      cockpit: origin,
      apiHealth: `${origin}/health`,
      metrics: `${origin}/api/ops/monitor`,
      coreHealth: `${origin}/core-health`,
      opsConsole: `${origin}/ops`,
      difyHealth: getDifyHealthUrl(),
    };
  }, []);

  return (
    <header className="sticky top-0 z-20 border-b border-border/80 bg-[linear-gradient(180deg,rgba(7,9,8,0.88),rgba(7,8,7,0.72))] px-4 py-4 backdrop-blur-xl md:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onMenuToggle}
              aria-controls="primary-sidebar"
              aria-expanded={navOpen}
              className="flex h-10 w-10 items-center justify-center rounded-2xl border border-border/80 bg-black/30 text-sm text-accent transition hover:border-accent/45 hover:bg-accent/10 lg:hidden"
              aria-label={navOpen ? "Close navigation" : "Open navigation"}
            >
              {navOpen ? "✕" : "☰"}
            </button>
            <span className="screen-label">{eyebrow}</span>
            <span className="hidden rounded-full border border-border/80 bg-black/25 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-amber-100/42 md:inline">
              {section}
            </span>
            <span className="hidden rounded-full border border-accent/25 bg-accent/6 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-accent md:inline">
              lane {index}
            </span>
            <span className="hidden text-[11px] uppercase tracking-[0.22em] text-amber-100/38 md:inline">
              {clockLabel}
            </span>
          </div>
          <div className="mt-3 flex flex-col gap-2 xl:flex-row xl:items-end xl:gap-5">
            <h1 className="text-2xl font-semibold uppercase tracking-[0.18em] text-accent glow-text md:text-[2rem]">
              {title}
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-amber-100/58 md:text-[15px]">
              {description}
            </p>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              to="/ops"
              className="status-chip min-h-0 border-border/80 bg-black/25 px-3 py-2 text-muted transition hover:border-accent/35 hover:text-accent"
            >
              ops hub
            </Link>
            <Link
              to="/agents/agent-zero"
              className="status-chip min-h-0 border-accent/28 bg-accent/8 px-3 py-2 text-accent transition hover:border-accent/45 hover:bg-accent/12"
            >
              agent zero
            </Link>
            <a
              href={endpoints.difyHealth}
              target="_blank"
              rel="noreferrer"
              className="status-chip min-h-0 border-border/80 bg-black/25 px-3 py-2 text-muted transition hover:border-accent/35 hover:text-accent"
            >
              dify health
            </a>
            <a
              href={endpoints.apiHealth}
              target="_blank"
              rel="noreferrer"
              className="status-chip min-h-0 border-border/80 bg-black/25 px-3 py-2 text-muted transition hover:border-accent/35 hover:text-accent"
            >
              api health
            </a>
            <a
              href={endpoints.coreHealth}
              target="_blank"
              rel="noreferrer"
              className="status-chip min-h-0 border-border/80 bg-black/25 px-3 py-2 text-muted transition hover:border-accent/35 hover:text-accent"
            >
              core health
            </a>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 md:justify-end">
          <span className={["status-chip", statusTone(apiOk)].join(" ")}>
            API {apiOk ? "ONLINE" : "DOWN"}
          </span>
          <span className={["status-chip", statusTone(coreOk)].join(" ")}>
            CORE {coreOk ? "ONLINE" : "DOWN"}
          </span>
          <span
            className={[
              "status-chip",
              authReady
                ? "border-accent/35 bg-accent/10 text-accent"
                : "border-border/80 bg-black/25 text-muted",
            ].join(" ")}
          >
            AUTH {authReady ? "LOADED" : "MISSING"}
          </span>

          <div className="relative" ref={ref}>
            <button
              type="button"
              onClick={() => setOpen((current) => !current)}
              aria-expanded={open}
              aria-haspopup="dialog"
              aria-controls={open ? sessionPanelId : undefined}
              className="flex h-10 items-center gap-2 rounded-2xl border border-border/80 bg-black/30 px-3 text-xs uppercase tracking-[0.18em] text-amber-100/74 transition hover:border-accent/45 hover:text-accent"
              title="API Key"
            >
              <span className="text-sm">🔑</span>
              session
            </button>
            {open && (
              <div
                id={sessionPanelId}
                role="dialog"
                aria-modal="false"
                aria-labelledby={sessionTitleId}
                data-shortcuts-lock="true"
                className="absolute right-0 top-14 z-50 max-h-[min(78vh,34rem)] w-[min(26rem,calc(100vw-1rem))] overflow-y-auto overscroll-contain rounded-3xl border border-border/80 bg-[linear-gradient(180deg,rgba(7,7,7,0.98),rgba(10,11,10,0.96))] p-4 pr-3 shadow-[0_24px_80px_rgba(0,0,0,0.45)]"
              >
                <div className="space-y-4">
                  <div className="space-y-1">
                    <p className="screen-label">session control</p>
                    <h3
                      id={sessionTitleId}
                      className="text-sm font-semibold uppercase tracking-[0.18em] text-accent"
                    >
                      Auth and runtime endpoints
                    </h3>
                    <p className="text-[12px] leading-5 text-amber-100/50">
                      Gere le bearer token local et garde sous la main les points d'entree utiles du cockpit.
                    </p>
                  </div>

                  <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[10px] uppercase tracking-[0.2em] text-muted">gateway auth</p>
                        <p className="mt-1 text-[12px] leading-5 text-amber-100/60">
                          Cookie local utilise pour appeler l'API Mascarade.
                        </p>
                      </div>
                      <span
                        className={[
                          "status-chip min-h-0 px-3 py-2",
                          authReady
                            ? "border-accent/35 bg-accent/10 text-accent"
                            : "border-border/80 bg-black/25 text-muted",
                        ].join(" ")}
                      >
                        {authReady ? "loaded" : "missing"}
                      </span>
                    </div>

                    <label className="mb-2 block text-[11px] uppercase tracking-[0.18em] text-muted">
                      API Key
                    </label>
                    <div className="flex gap-2">
                      <input
                        ref={inputRef}
                        type={showKey ? "text" : "password"}
                        value={draftKey}
                        onChange={(e) => { setDraftKey(e.target.value); setKeyStatus("idle"); }}
                        className="min-w-0 flex-1 rounded-2xl border border-border/80 bg-black/35 px-3 py-3 text-sm text-amber-100 outline-none transition focus:border-accent/50"
                        placeholder="Enter your API key"
                      />
                      <Button
                        variant="ghost"
                        type="button"
                        className="px-3"
                        onClick={() => setShowKey((current) => !current)}
                      >
                        {showKey ? "hide" : "show"}
                      </Button>
                    </div>

                    {keyStatus === "invalid" && (
                      <p className="mt-2 text-[12px] text-red-400">
                        Cle invalide — verifiez le token ou la connectivite API.
                      </p>
                    )}
                    {keyStatus === "valid" && (
                      <p className="mt-2 text-[12px] text-emerald-400">
                        Cle validee.
                      </p>
                    )}

                    <label className="mt-3 flex cursor-pointer items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted">
                      <input
                        type="checkbox"
                        checked={persist}
                        onChange={(e) => setPersist(e.target.checked)}
                        className="accent-accent"
                      />
                      Retenir 30 jours
                    </label>

                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                      <span className="text-[11px] uppercase tracking-[0.16em] text-amber-100/40">
                        {savedAt ? `saved ${savedAt}${persist ? " (30d)" : ""}` : authReady ? "key present" : "no key loaded"}
                      </span>
                      <div className="flex flex-wrap gap-2">
                        <Button variant="ghost" type="button" onClick={clear}>
                          clear
                        </Button>
                        <Button type="button" onClick={save} disabled={keyStatus === "checking"}>
                          {keyStatus === "checking" ? "check..." : "save"}
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4">
                    <div className="mb-3">
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">runtime links</p>
                      <p className="mt-1 text-[12px] leading-5 text-amber-100/60">
                        Acces rapide aux endpoints utiles pour debug et supervision.
                      </p>
                    </div>
                    <div className="grid gap-2">
                      <a
                        href={endpoints.cockpit}
                        className="rounded-2xl border border-border/80 bg-black/30 px-3 py-3 text-[11px] uppercase tracking-[0.16em] text-amber-100/68 transition hover:border-accent/35 hover:text-accent"
                      >
                        cockpit
                        <span className="mt-1 block normal-case tracking-normal text-amber-100/38">
                          {endpoints.cockpit}
                        </span>
                      </a>
                      <a
                        href={endpoints.metrics}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-2xl border border-border/80 bg-black/30 px-3 py-3 text-[11px] uppercase tracking-[0.16em] text-amber-100/68 transition hover:border-accent/35 hover:text-accent"
                      >
                        ops monitor
                        <span className="mt-1 block normal-case tracking-normal text-amber-100/38">
                          {endpoints.metrics}
                        </span>
                      </a>
                      <a
                        href={endpoints.coreHealth}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-2xl border border-border/80 bg-black/30 px-3 py-3 text-[11px] uppercase tracking-[0.16em] text-amber-100/68 transition hover:border-accent/35 hover:text-accent"
                      >
                        core health
                        <span className="mt-1 block normal-case tracking-normal text-amber-100/38">
                          {endpoints.coreHealth}
                        </span>
                      </a>
                    </div>
                  </div>

                  <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4">
                    <div className="mb-3">
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">keyboard lane</p>
                      <p className="mt-1 text-[12px] leading-5 text-amber-100/60">
                        Raccourcis exposes directement dans le shell pour garder une navigation rapide au clavier.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="status-chip min-h-0 border-border/80 bg-black/30 px-3 py-2 text-muted">
                        Alt+1..8 switch lane
                      </span>
                      <span className="status-chip min-h-0 border-border/80 bg-black/30 px-3 py-2 text-muted">
                        Esc close panels
                      </span>
                      <span className="status-chip min-h-0 border-border/80 bg-black/30 px-3 py-2 text-muted">
                        Tab trap modal
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

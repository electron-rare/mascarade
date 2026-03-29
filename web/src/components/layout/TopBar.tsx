import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getApiKey, isPersisted, api, post, put } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { getDifyHealthUrl } from "../../lib/dify";
import Button from "../ui/Button";

interface HealthData {
  status: string;
  auth_required?: boolean;
  core?: { status: string };
}

interface QuickProviderFieldStatus {
  env: string;
  label: string;
  configured: boolean;
  hint: string;
  secret: boolean;
  active?: boolean;
}

interface QuickProviderStatus {
  name: string;
  label: string;
  configured: boolean;
  active: boolean;
  fields: QuickProviderFieldStatus[];
  auth_mode?: string;
  auth_mode_env?: string;
  toggle_env?: string;
}

interface QuickProviderMutationResponse {
  status: string;
  active: boolean;
  configured: boolean;
  message?: string;
  restarted_services?: string[];
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
    ? "border-emerald-200 bg-emerald-50 text-emerald-600"
    : "border-red-200 bg-red-50 text-error";
}

function resolveQuickProviderField(provider: QuickProviderStatus) {
  if (provider.toggle_env) {
    return null;
  }

  if (provider.auth_mode_env && provider.auth_mode !== "api_key") {
    return null;
  }

  const visibleFields = provider.fields.filter((field) => field.active !== false);
  if (visibleFields.length !== 1) {
    return null;
  }

  const [field] = visibleFields;
  return field.secret ? field : null;
}

function sortQuickProviders(providers: QuickProviderStatus[]) {
  const order = ["claude", "openai", "mistral", "google", "huggingface"];
  return [...providers].sort((left, right) => {
    const leftIndex = order.indexOf(left.name);
    const rightIndex = order.indexOf(right.name);
    if (leftIndex === -1 && rightIndex === -1) {
      return left.label.localeCompare(right.label);
    }
    if (leftIndex === -1) {
      return 1;
    }
    if (rightIndex === -1) {
      return -1;
    }
    return leftIndex - rightIndex;
  });
}

function quickProviderTone(provider: QuickProviderStatus) {
  if (provider.active) {
    return "border-emerald-200 bg-emerald-50 text-emerald-600";
  }
  if (provider.configured) {
    return "border-amber-200 bg-amber-50 text-[#1d1d1f]";
  }
  return "border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-[#86868b]";
}

function QuickProviderKeyCard({
  provider,
  onSaved,
}: {
  provider: QuickProviderStatus;
  onSaved: () => Promise<void>;
}) {
  const field = resolveQuickProviderField(provider);
  const [draft, setDraft] = useState("");
  const [showValue, setShowValue] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "ok" | "error">("idle");
  const [message, setMessage] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
  }, []);

  if (!field) {
    return null;
  }

  const settle = (nextState: "idle" | "saving" | "ok" | "error", nextMessage: string) => {
    setSaveState(nextState);
    setMessage(nextMessage);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    if (nextState === "ok" || nextState === "error") {
      timerRef.current = setTimeout(() => {
        setSaveState("idle");
        setMessage("");
      }, 4000);
    }
  };

  const save = async () => {
    const value = draft.trim();
    if (!value) {
      settle("error", "Colle une cle avant de sauvegarder.");
      return;
    }

    setSaveState("saving");
    try {
      const result = await put<QuickProviderMutationResponse>(
        `/api/agents/providers/${provider.name}/key`,
        { keys: { [field.env]: value } },
      );
      setDraft("");
      await onSaved();
      settle(
        "ok",
        result.restarted_services?.length
          ? `${provider.label} mis a jour, restart: ${result.restarted_services.join(", ")}`
          : result.active
            ? `${provider.label} actif`
            : result.message || `${provider.label} configure`,
      );
    } catch (error) {
      settle("error", error instanceof Error ? error.message : "Erreur");
    }
  };

  const clearValue = async () => {
    if (!provider.configured && !draft.trim()) {
      return;
    }

    if (!provider.configured && draft.trim()) {
      setDraft("");
      settle("ok", "Brouillon efface");
      return;
    }

    setSaveState("saving");
    try {
      const result = await post<QuickProviderMutationResponse>(
        `/api/agents/providers/${provider.name}/clear`,
        { fields: [field.env] },
      );
      setDraft("");
      await onSaved();
      settle(
        "ok",
        result.restarted_services?.length
          ? `${provider.label} efface, restart: ${result.restarted_services.join(", ")}`
          : result.message || `${provider.label} efface`,
      );
    } catch (error) {
      settle("error", error instanceof Error ? error.message : "Erreur");
    }
  };

  return (
    <div className="rounded-xl border border-[rgba(0,0,0,0.08)] bg-white p-3 shadow-[0_2px_8px_rgba(0,0,0,0.04)]">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-accent">
            {provider.label}
          </p>
          <p className="mt-1 text-[11px] text-[#86868b]">
            {field.env}
          </p>
        </div>
        <span className={["rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]", quickProviderTone(provider)].join(" ")}>
          {provider.active ? "active" : provider.configured ? "configured" : "missing"}
        </span>
      </div>

      <div className="flex gap-2">
        <input
          type={showValue ? "text" : "password"}
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            if (saveState !== "idle") {
              setSaveState("idle");
              setMessage("");
            }
          }}
          placeholder={field.configured ? field.hint || "Configured" : "Paste API key"}
          className="min-w-0 flex-1 rounded-lg border border-[rgba(0,0,0,0.08)] bg-white px-3 py-2.5 text-sm text-[#1d1d1f] outline-none transition placeholder:text-[#86868b]/50 focus:border-accent/50 focus:ring-2 focus:ring-accent/10"
        />
        <Button
          variant="ghost"
          type="button"
          className="px-3"
          onClick={() => setShowValue((current) => !current)}
        >
          {showValue ? "hide" : "show"}
        </Button>
      </div>

      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          {message ? (
            <p className={["text-[11px]", saveState === "ok" ? "text-emerald-500" : "text-red-500"].join(" ")}>
              {message}
            </p>
          ) : (
            <p className="text-[11px] text-[#86868b]">
              {provider.configured ? "Cle deja presente, colle une nouvelle valeur pour la remplacer." : "Ajout rapide sans passer par Settings."}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="ghost"
            type="button"
            onClick={clearValue}
            disabled={saveState === "saving" || (!provider.configured && !draft.trim())}
          >
            clear
          </Button>
          <Button type="button" onClick={save} disabled={saveState === "saving" || !draft.trim()}>
            {saveState === "saving" ? "save..." : "save"}
          </Button>
        </div>
      </div>
    </div>
  );
}


function DarkModeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme === "dark");

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "dark") {
      document.documentElement.dataset.theme = "dark";
      setDark(true);
    }
  }, []);

  return (
    <button
      onClick={toggle}
      className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-[#f5f5f7] hover:bg-[rgba(0,0,0,0.06)] transition-colors text-sm"
      title={dark ? "Mode clair" : "Mode sombre"}
      aria-label={dark ? "Mode clair" : "Mode sombre"}
    >
      {dark ? "☀" : "☾"}
    </button>
  );
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
  const [quickProviders, setQuickProviders] = useState<QuickProviderStatus[]>([]);
  const [quickProvidersLoading, setQuickProvidersLoading] = useState(false);
  const [quickProvidersError, setQuickProvidersError] = useState("");
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

  useEffect(() => {
    if (!open) {
      return;
    }

    if (!storedKey.trim()) {
      setQuickProviders([]);
      setQuickProvidersError("Charge d'abord la cle gateway pour administrer les providers.");
      setQuickProvidersLoading(false);
      return;
    }

    let cancelled = false;
    const loadQuickProviders = async () => {
      setQuickProvidersLoading(true);
      try {
        const response = await api<{ providers: QuickProviderStatus[] }>("/api/agents/providers/status");
        if (cancelled) {
          return;
        }
        const nextProviders = sortQuickProviders(
          response.providers.filter((provider) => !!resolveQuickProviderField(provider)),
        );
        setQuickProviders(nextProviders);
        setQuickProvidersError("");
      } catch (error) {
        if (cancelled) {
          return;
        }
        setQuickProviders([]);
        setQuickProvidersError(error instanceof Error ? error.message : "Impossible de charger les providers.");
      } finally {
        if (!cancelled) {
          setQuickProvidersLoading(false);
        }
      }
    };

    void loadQuickProviders();
    return () => {
      cancelled = true;
    };
  }, [open, storedKey]);

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
    <header className="sticky top-0 z-20 border-b border-[rgba(0,0,0,0.06)] bg-[rgba(255,255,255,0.72)] px-4 py-4 backdrop-blur-xl backdrop-saturate-[1.8] md:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onMenuToggle}
              aria-controls="primary-sidebar"
              aria-expanded={navOpen}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-sm text-[#1d1d1f] transition hover:bg-[#e8e8ed] hover:text-accent lg:hidden"
              aria-label={navOpen ? "Close navigation" : "Open navigation"}
            >
              {navOpen ? "✕" : "☰"}
            </button>
            <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-[#86868b]">{eyebrow}</span>
            <span className="hidden rounded-full border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-[#86868b] md:inline">
              {section}
            </span>
            <span className="hidden rounded-full border border-accent/15 bg-accent/6 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-accent md:inline">
              lane {index}
            </span>
            <span className="hidden text-[11px] uppercase tracking-[0.22em] text-[#86868b] md:inline">
              {clockLabel}
            </span>
          </div>
          <div className="mt-3 flex flex-col gap-2 xl:flex-row xl:items-end xl:gap-5">
            <h1 className="text-2xl font-semibold uppercase tracking-[0.18em] text-[#1d1d1f] md:text-[2rem]">
              {title}
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-[#86868b] md:text-[15px]">
              {description}
            </p>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              to="/admin"
              className="rounded-full border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#86868b] transition hover:bg-[#e8e8ed] hover:text-accent"
            >
              ops hub
            </Link>
            <Link
              to="/agents/agent-zero"
              className="rounded-full border border-accent/20 bg-accent/8 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-accent transition hover:bg-accent/12"
            >
              agent zero
            </Link>
            <a
              href={endpoints.difyHealth}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#86868b] transition hover:bg-[#e8e8ed] hover:text-accent"
            >
              dify health
            </a>
            <a
              href={endpoints.apiHealth}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#86868b] transition hover:bg-[#e8e8ed] hover:text-accent"
            >
              api health
            </a>
            <a
              href={endpoints.coreHealth}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#86868b] transition hover:bg-[#e8e8ed] hover:text-accent"
            >
              core health
            </a>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 md:justify-end">
          <span className={["rounded-full px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em]", statusTone(apiOk)].join(" ")}>
            API {apiOk ? "ONLINE" : "DOWN"}
          </span>
          <span className={["rounded-full px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em]", statusTone(coreOk)].join(" ")}>
            CORE {coreOk ? "ONLINE" : "DOWN"}
          </span>
          <span
            className={[
              "rounded-full px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em]",
              authReady
                ? "border-accent/20 bg-accent/8 text-accent"
                : "border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-[#86868b]",
            ].join(" ")}
          >
            AUTH {authReady ? "LOADED" : "MISSING"}
          </span>

          <DarkModeToggle />
          <div className="relative" ref={ref}>
            <button
              type="button"
              onClick={() => setOpen((current) => !current)}
              aria-expanded={open}
              aria-haspopup="dialog"
              aria-controls={open ? sessionPanelId : undefined}
              className="flex h-10 items-center gap-2 rounded-xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 text-xs uppercase tracking-[0.18em] text-[#6e6e73] transition hover:bg-[#e8e8ed] hover:text-accent"
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
                className="absolute right-0 top-14 z-50 max-h-[min(78vh,34rem)] w-[min(26rem,calc(100vw-1rem))] overflow-y-auto overscroll-contain rounded-2xl border border-[rgba(0,0,0,0.08)] bg-white p-4 pr-3 shadow-[0_8px_40px_rgba(0,0,0,0.12)]"
              >
                <div className="space-y-4">
                  <div className="space-y-1">
                    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[#86868b]">session control</p>
                    <h3
                      id={sessionTitleId}
                      className="text-sm font-semibold uppercase tracking-[0.18em] text-accent"
                    >
                      Auth and runtime endpoints
                    </h3>
                    <p className="text-[12px] leading-5 text-[#86868b]">
                      Gere le bearer token local et garde sous la main les points d'entree utiles du cockpit.
                    </p>
                  </div>

                  <div className="rounded-xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[10px] uppercase tracking-[0.2em] text-[#86868b]">gateway auth</p>
                        <p className="mt-1 text-[12px] leading-5 text-[#6e6e73]">
                          Cookie local utilise pour appeler l'API Mascarade.
                        </p>
                      </div>
                      <span
                        className={[
                          "rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]",
                          authReady
                            ? "border-accent/20 bg-accent/8 text-accent"
                            : "border-[rgba(0,0,0,0.08)] bg-white text-[#86868b]",
                        ].join(" ")}
                      >
                        {authReady ? "loaded" : "missing"}
                      </span>
                    </div>

                    <label className="mb-2 block text-[11px] uppercase tracking-[0.18em] text-[#86868b]">
                      API Key
                    </label>
                    <div className="flex gap-2">
                      <input
                        ref={inputRef}
                        type={showKey ? "text" : "password"}
                        value={draftKey}
                        onChange={(e) => { setDraftKey(e.target.value); setKeyStatus("idle"); }}
                        className="min-w-0 flex-1 rounded-lg border border-[rgba(0,0,0,0.08)] bg-white px-3 py-3 text-sm text-[#1d1d1f] outline-none transition placeholder:text-[#86868b]/50 focus:border-accent/50 focus:ring-2 focus:ring-accent/10"
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
                      <p className="mt-2 text-[12px] text-red-500">
                        Cle invalide — verifiez le token ou la connectivite API.
                      </p>
                    )}
                    {keyStatus === "valid" && (
                      <p className="mt-2 text-[12px] text-emerald-500">
                        Cle validee.
                      </p>
                    )}

                    <label className="mt-3 flex cursor-pointer items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-[#86868b]">
                      <input
                        type="checkbox"
                        checked={persist}
                        onChange={(e) => setPersist(e.target.checked)}
                        className="accent-accent"
                      />
                      Retenir 30 jours
                    </label>

                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                      <span className="text-[11px] uppercase tracking-[0.16em] text-[#86868b]">
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

                  <div className="rounded-xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                    <div className="mb-3 flex items-start justify-between gap-3">
                      <div>
                        <p className="text-[10px] uppercase tracking-[0.2em] text-[#86868b]">provider quick keys</p>
                        <p className="mt-1 text-[12px] leading-5 text-[#6e6e73]">
                          Ajoute ou remplace les cles simples sans quitter le menu session. Les cas OAuth ou multi-champs restent dans Settings.
                        </p>
                      </div>
                      <Link
                        to="/admin"
                        onClick={() => setOpen(false)}
                        className="rounded-full border border-accent/20 bg-accent/8 px-3 py-1.5 text-[10px] uppercase tracking-[0.16em] text-accent transition hover:bg-accent/12"
                      >
                        settings
                      </Link>
                    </div>

                    {!authReady ? (
                      <p className="text-[12px] text-[#86868b]">
                        Charge d'abord la cle gateway ci-dessus, puis les providers editables apparaissent ici.
                      </p>
                    ) : quickProvidersLoading ? (
                      <p className="text-[12px] text-[#86868b]">
                        Sync providers...
                      </p>
                    ) : quickProvidersError ? (
                      <p className="text-[12px] text-red-500">
                        {quickProvidersError}
                      </p>
                    ) : quickProviders.length > 0 ? (
                      <div className="grid gap-3">
                        {quickProviders.map((provider) => (
                          <QuickProviderKeyCard
                            key={provider.name}
                            provider={provider}
                            onSaved={async () => {
                              const response = await api<{ providers: QuickProviderStatus[] }>("/api/agents/providers/status");
                              setQuickProviders(
                                sortQuickProviders(
                                  response.providers.filter((entry) => !!resolveQuickProviderField(entry)),
                                ),
                              );
                              setQuickProvidersError("");
                            }}
                          />
                        ))}
                      </div>
                    ) : (
                      <p className="text-[12px] text-[#86868b]">
                        Aucun provider a cle simple disponible ici. Utilise Settings pour les integrations OAuth ou multi-secrets.
                      </p>
                    )}
                  </div>

                  <div className="rounded-xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                    <div className="mb-3">
                      <p className="text-[10px] uppercase tracking-[0.2em] text-[#86868b]">runtime links</p>
                      <p className="mt-1 text-[12px] leading-5 text-[#6e6e73]">
                        Acces rapide aux endpoints utiles pour debug et supervision.
                      </p>
                    </div>
                    <div className="grid gap-2">
                      <a
                        href={endpoints.cockpit}
                        className="rounded-lg border border-[rgba(0,0,0,0.06)] bg-white px-3 py-3 text-[11px] uppercase tracking-[0.16em] text-[#6e6e73] transition hover:border-accent/20 hover:text-accent"
                      >
                        cockpit
                        <span className="mt-1 block normal-case tracking-normal text-[#86868b]">
                          {endpoints.cockpit}
                        </span>
                      </a>
                      <a
                        href={endpoints.metrics}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-lg border border-[rgba(0,0,0,0.06)] bg-white px-3 py-3 text-[11px] uppercase tracking-[0.16em] text-[#6e6e73] transition hover:border-accent/20 hover:text-accent"
                      >
                        ops monitor
                        <span className="mt-1 block normal-case tracking-normal text-[#86868b]">
                          {endpoints.metrics}
                        </span>
                      </a>
                      <a
                        href={endpoints.coreHealth}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-lg border border-[rgba(0,0,0,0.06)] bg-white px-3 py-3 text-[11px] uppercase tracking-[0.16em] text-[#6e6e73] transition hover:border-accent/20 hover:text-accent"
                      >
                        core health
                        <span className="mt-1 block normal-case tracking-normal text-[#86868b]">
                          {endpoints.coreHealth}
                        </span>
                      </a>
                    </div>
                  </div>

                  <div className="rounded-xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                    <div className="mb-3">
                      <p className="text-[10px] uppercase tracking-[0.2em] text-[#86868b]">keyboard lane</p>
                      <p className="mt-1 text-[12px] leading-5 text-[#6e6e73]">
                        Raccourcis exposes directement dans le shell pour garder une navigation rapide au clavier.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full border border-[rgba(0,0,0,0.08)] bg-white px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.16em] text-[#86868b] shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
                        Alt+1..8 switch lane
                      </span>
                      <span className="rounded-full border border-[rgba(0,0,0,0.08)] bg-white px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.16em] text-[#86868b] shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
                        Esc close panels
                      </span>
                      <span className="rounded-full border border-[rgba(0,0,0,0.08)] bg-white px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.16em] text-[#86868b] shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
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

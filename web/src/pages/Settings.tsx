import { useCallback, useEffect, useRef, useState } from "react";
import { get, isPersisted, post, put } from "../api/client";
import { useAuth } from "../auth/AuthContext";

interface FieldStatus {
  env: string;
  label: string;
  configured: boolean;
  hint: string;
  secret: boolean;
  classification?: string;
  criticality?: string;
  auth_modes?: string[];
}

interface ProviderStatus {
  name: string;
  label: string;
  classification?: string;
  criticality?: string;
  required_when?: string;
  used_by?: string[];
  configured: boolean;
  active: boolean;
  fields: FieldStatus[];
  default_model: string | null;
  models: string[];
  enabled?: boolean;
  toggle_env?: string;
  auth_mode?: string;
  auth_mode_env?: string;
  auth_modes?: string[];
}

interface ProviderMutationResponse {
  status: string;
  active: boolean;
  configured: boolean;
  message?: string;
  updated_env?: string[];
  cleared_env?: string[];
  restarted_services?: string[];
}

interface RuntimeSecretFieldStatus {
  env: string;
  label: string;
  configured: boolean;
  hint: string;
  secret: boolean;
  classification?: string;
  criticality?: string;
  restart_services: string[];
  auth_modes?: string[];
  active?: boolean;
}

interface RuntimeSecretGroupStatus {
  name: string;
  label: string;
  description: string;
  classification?: string;
  criticality?: string;
  required_when?: string;
  used_by?: string[];
  configured: boolean;
  configured_count: number;
  field_count: number;
  generate_supported: boolean;
  restart_services: string[];
  fields: RuntimeSecretFieldStatus[];
  auth_mode?: string;
  auth_mode_env?: string;
  auth_modes?: string[];
}

interface RuntimeSecretMutationResponse {
  status: string;
  message?: string;
  group: RuntimeSecretGroupStatus;
  updated_env?: string[];
  cleared_env?: string[];
  restarted_services?: string[];
  client_token?: string;
  generated_value?: string;
}

type SaveState = "idle" | "saving" | "ok" | "error";

function criticalityMeta(level?: string) {
  switch (level) {
    case "required-security":
      return {
        label: "required security",
        className: "border-red-700/60 bg-red-900/20 text-red-300",
      };
    case "feature-required":
      return {
        label: "feature required",
        className: "border-amber-600/40 bg-amber-900/20 text-amber-300",
      };
    case "live-validation-optional":
      return {
        label: "live optional",
        className: "border-sky-700/40 bg-sky-900/20 text-sky-300",
      };
    case "local-operator-context":
      return {
        label: "operator context",
        className: "border-border/80 bg-black/25 text-muted",
      };
    default:
      return {
        label: level || "unclassified",
        className: "border-border/80 bg-black/25 text-muted",
      };
  }
}

function classificationLabel(kind?: string) {
  switch (kind) {
    case "runtime-auth":
      return "runtime auth";
    case "provider-credential":
      return "provider credential";
    case "integration-credential":
      return "integration credential";
    case "oauth-config":
      return "oauth config";
    case "live-validation-target":
      return "live validation target";
    case "operator-context":
      return "operator context";
    default:
      return kind || "";
  }
}

function CriticalityChip({ level }: { level?: string }) {
  const meta = criticalityMeta(level);
  return (
    <span className={`status-chip ${meta.className}`}>
      {meta.label}
    </span>
  );
}

function MetaLine({
  criticality,
  classification,
  requiredWhen,
  usedBy,
}: {
  criticality?: string;
  classification?: string;
  requiredWhen?: string;
  usedBy?: string[];
}) {
  const classificationText = classificationLabel(classification);
  const usedByText = usedBy?.length ? usedBy.join(", ") : "";
  return (
    <div className="mt-2 space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <CriticalityChip level={criticality} />
        {classificationText && (
          <span className="status-chip border-border/80 bg-black/25 text-muted">
            {classificationText}
          </span>
        )}
      </div>
      {requiredWhen && (
        <p className="text-[11px] leading-5 text-amber-100/45">
          {requiredWhen}
        </p>
      )}
      {usedByText && (
        <p className="text-[11px] leading-5 text-amber-100/32">
          used by: {usedByText}
        </p>
      )}
    </div>
  );
}

function StatusBadge({ active, configured }: { active: boolean; configured: boolean }) {
  if (active) {
    return (
      <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">
        active
      </span>
    );
  }
  if (configured) {
    return (
      <span className="status-chip border-amber-600/40 bg-amber-900/20 text-amber-400">
        configured
      </span>
    );
  }
  return (
    <span className="status-chip border-border/80 bg-black/25 text-muted">
      missing
    </span>
  );
}

function RuntimeBadge({
  configured,
  configuredCount,
  fieldCount,
}: {
  configured: boolean;
  configuredCount: number;
  fieldCount: number;
}) {
  if (configuredCount === fieldCount && fieldCount > 0) {
    return (
      <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">
        ready
      </span>
    );
  }
  if (configured) {
    return (
      <span className="status-chip border-amber-600/40 bg-amber-900/20 text-amber-400">
        partial
      </span>
    );
  }
  return (
    <span className="status-chip border-border/80 bg-black/25 text-muted">
      missing
    </span>
  );
}

function ProviderCard({
  provider,
  onSaved,
}: {
  provider: ProviderStatus;
  onSaved: () => void | Promise<void>;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [message, setMessage] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const selectedAuthMode =
    provider.auth_mode_env && drafts[provider.auth_mode_env] !== undefined
      ? drafts[provider.auth_mode_env]
      : provider.auth_mode;

  const settle = (nextState: SaveState, nextMessage: string) => {
    setSaveState(nextState);
    setMessage(nextMessage);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setSaveState("idle");
      setMessage("");
    }, 5000);
  };

  const setField = (env: string, value: string) => {
    setDrafts((prev) => ({ ...prev, [env]: value }));
    setSaveState("idle");
    setMessage("");
  };

  const clearDraftField = (env: string) => {
    setDrafts((prev) => {
      if (!(env in prev)) {
        return prev;
      }
      const next = { ...prev };
      delete next[env];
      return next;
    });
    setSaveState("idle");
    setMessage("");
  };

  const save = async () => {
    const keys: Record<string, string> = {};
    const visibleFields = provider.fields.filter((field) => {
      if (!field.auth_modes?.length) {
        return true;
      }
      return !!selectedAuthMode && field.auth_modes.includes(selectedAuthMode);
    });
    for (const field of visibleFields) {
      const val = drafts[field.env];
      if (val !== undefined && val !== "") {
        keys[field.env] = val;
      }
    }
    if (provider.toggle_env && drafts[provider.toggle_env] !== undefined) {
      keys[provider.toggle_env] = drafts[provider.toggle_env];
    }
    if (provider.auth_mode_env && drafts[provider.auth_mode_env] !== undefined) {
      keys[provider.auth_mode_env] = drafts[provider.auth_mode_env];
    }
    if (Object.keys(keys).length === 0) {
      setMessage("Aucune valeur a sauvegarder");
      setSaveState("error");
      return;
    }

    setSaveState("saving");
    try {
      const res = await put<ProviderMutationResponse>(
        `/api/agents/providers/${provider.name}/key`,
        { keys },
      );
      setSaveState("ok");
      setMessage(
        res.active
          ? res.restarted_services?.length
            ? `Provider actif, restart: ${res.restarted_services.join(", ")}`
            : "Provider actif"
          : res.message || "Sauvegarde mais pas actif",
      );
      setDrafts({});
      await onSaved();
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        setSaveState("idle");
        setMessage("");
      }, 4000);
    } catch (err) {
      setSaveState("error");
      setMessage(err instanceof Error ? err.message : "Erreur");
    }
  };

  const clearProvider = async (fields?: string[], scopeLabel?: string) => {
    if (fields?.length === 1) {
      const [fieldEnv] = fields;
      const field = provider.fields.find((entry) => entry.env === fieldEnv);
      if (field && !field.configured && drafts[fieldEnv] !== undefined) {
        clearDraftField(fieldEnv);
        settle("ok", `${field.label} efface du brouillon`);
        return;
      }
    }

    setSaveState("saving");
    try {
      const res = await post<ProviderMutationResponse>(
        `/api/agents/providers/${provider.name}/clear`,
        fields?.length ? { fields } : undefined,
      );
      if (fields?.length) {
        setDrafts((prev) => {
          const next = { ...prev };
          for (const field of fields) {
            delete next[field];
          }
          return next;
        });
      } else {
        setDrafts({});
      }
      await onSaved();
      settle(
        "ok",
        res.restarted_services?.length
          ? `${scopeLabel || "Valeurs"} efface${fields?.length === 1 ? "e" : "es"}, restart: ${res.restarted_services.join(", ")}`
          : res.message || `${scopeLabel || "Valeurs"} efface${fields?.length === 1 ? "e" : "es"}`,
      );
    } catch (err) {
      setSaveState("error");
      setMessage(err instanceof Error ? err.message : "Erreur");
    }
  };

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const payload = event.data;
      if (!payload || typeof payload !== "object") {
        return;
      }
      if ((payload as { type?: string }).type !== "mascarade-oauth-result") {
        return;
      }
      const targetProvider = (payload as { provider?: string }).provider;
      if (targetProvider !== provider.name) {
        return;
      }
      const ok = (payload as { ok?: boolean }).ok === true;
      const nextMessage =
        typeof (payload as { message?: string }).message === "string"
          ? (payload as { message?: string }).message!
          : ok
            ? "OAuth linked"
            : "OAuth failed";
      void onSaved();
      settle(ok ? "ok" : "error", nextMessage);
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [onSaved, provider.name]);

  const connectProviderOAuth = () => {
    const popup = window.open(
      `/api/settings/providers/${provider.name}/oauth/start`,
      `mascarade-${provider.name}-oauth`,
      "popup=yes,width=720,height=820",
    );
    if (!popup) {
      settle("error", "Popup bloquee");
      return;
    }
    settle("ok", `OAuth ${provider.label} en cours...`);
  };

  const visibleFields = provider.fields.filter((field) => {
    if (!field.auth_modes?.length) {
      return true;
    }
    return !!selectedAuthMode && field.auth_modes.includes(selectedAuthMode);
  });
  const hasDraft = visibleFields.some((field) => drafts[field.env]?.trim()) ||
    (!!provider.auth_mode_env && drafts[provider.auth_mode_env] !== undefined) ||
    (!!provider.toggle_env && drafts[provider.toggle_env] !== undefined);
  const canClear =
    provider.active ||
    provider.configured ||
    (provider.enabled ?? false) ||
    provider.fields.some((field) => field.configured);
  const supportsOAuthPopup =
    selectedAuthMode === "oauth_oidc" &&
    (provider.name === "huggingface" || provider.name === "google");

  return (
    <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold uppercase tracking-[0.18em] text-accent">
            {provider.label}
          </p>
          <MetaLine
            criticality={provider.criticality}
            classification={provider.classification}
            requiredWhen={provider.required_when}
            usedBy={provider.used_by}
          />
          {provider.default_model && (
            <p className="mt-1 text-[11px] text-amber-100/45">
              {provider.default_model}
            </p>
          )}
        </div>
        <StatusBadge active={provider.active} configured={provider.configured} />
      </div>

      <div className="space-y-3">
        {provider.auth_mode_env && provider.auth_modes && provider.auth_modes.length > 1 && (
          <div>
            <label className="mb-1.5 flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-muted">
              <span>Auth mode</span>
              <span className="normal-case tracking-normal text-amber-100/35">
                {provider.auth_mode_env}
              </span>
            </label>
            <select
              value={selectedAuthMode ?? provider.auth_modes[0]}
              onChange={(e) => setField(provider.auth_mode_env!, e.target.value)}
              className="w-full rounded-2xl border border-border/80 bg-black/35 px-3 py-2.5 text-sm text-amber-100 outline-none transition focus:border-accent/50"
            >
              {provider.auth_modes.map((mode) => (
                <option key={mode} value={mode} className="bg-[#0a0a0a]">
                  {mode}
                </option>
              ))}
            </select>
          </div>
        )}

        {visibleFields.map((field) => (
          <div key={field.env}>
            <label className="mb-1.5 flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-muted">
              <span>{field.label}</span>
              <span className="flex items-center gap-2">
                {field.criticality && field.criticality !== provider.criticality && (
                  <CriticalityChip level={field.criticality} />
                )}
                <span className="normal-case tracking-normal text-amber-100/35">
                  {field.env}
                </span>
                <button
                  type="button"
                  disabled={
                    saveState === "saving" ||
                    (!field.configured && drafts[field.env] === undefined)
                  }
                  onClick={() => clearProvider([field.env], field.label)}
                  className="rounded-full border border-red-800/40 bg-red-900/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-red-300 transition hover:border-red-700/60 hover:bg-red-900/20 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  clear
                </button>
              </span>
            </label>
            <input
              type={field.secret ? "password" : "text"}
              placeholder={field.configured ? field.hint : "Non configure"}
              value={drafts[field.env] ?? ""}
              onChange={(e) => setField(field.env, e.target.value)}
              className="w-full rounded-2xl border border-border/80 bg-black/35 px-3 py-2.5 text-sm text-amber-100 outline-none transition placeholder:text-amber-100/25 focus:border-accent/50"
            />
          </div>
        ))}

        {provider.toggle_env !== undefined && (
          <label className="flex cursor-pointer items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted">
            <input
              type="checkbox"
              checked={
                drafts[provider.toggle_env] !== undefined
                  ? drafts[provider.toggle_env] === "true"
                  : provider.enabled ?? false
              }
              onChange={(e) =>
                setField(provider.toggle_env!, e.target.checked ? "true" : "false")
              }
              className="accent-accent"
            />
            Activer
          </label>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          {message && (
            <p
              className={[
                "text-[12px]",
                saveState === "ok" ? "text-emerald-400" : "text-red-400",
              ].join(" ")}
            >
              {message}
            </p>
          )}
          {provider.active && provider.models.length > 1 && (
            <p className="text-[11px] text-amber-100/35">
              {provider.models.length} modeles disponibles
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {supportsOAuthPopup && (
            <button
              type="button"
              disabled={saveState === "saving"}
              onClick={connectProviderOAuth}
              className="rounded-2xl border border-[#214e31] bg-[#0c170f]/80 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-[#8cffb7] transition hover:border-[#2d6942] hover:bg-[#0f2116] disabled:cursor-not-allowed disabled:opacity-40"
            >
              connect
            </button>
          )}
          <button
            type="button"
            disabled={!canClear || saveState === "saving"}
            onClick={() => clearProvider()}
            className="rounded-2xl border border-red-800/50 bg-red-900/10 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-red-300 transition hover:border-red-700/60 hover:bg-red-900/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            clear
          </button>
          <button
            type="button"
            disabled={(!hasDraft && !Object.keys(drafts).length) || saveState === "saving"}
            onClick={save}
            className="rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-accent transition hover:border-accent/50 hover:bg-accent/18 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saveState === "saving" ? "..." : "save"}
          </button>
        </div>
      </div>
    </div>
  );
}

function RuntimeSecretCard({
  group,
  onSaved,
}: {
  group: RuntimeSecretGroupStatus;
  onSaved: () => Promise<void>;
}) {
  const { login, logout } = useAuth();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [message, setMessage] = useState("");
  const [generatedValue, setGeneratedValue] = useState("");
  const [extraInfo, setExtraInfo] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const selectedAuthMode =
    group.auth_mode_env && drafts[group.auth_mode_env] !== undefined
      ? drafts[group.auth_mode_env]
      : group.auth_mode;

  const setField = (env: string, value: string) => {
    setDrafts((prev) => ({ ...prev, [env]: value }));
    setSaveState("idle");
    setMessage("");
    setExtraInfo("");
  };

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  useEffect(() => {
    if (group.name !== "notion") {
      return;
    }
    const handleMessage = (event: MessageEvent) => {
      const payload = event.data;
      if (!payload || typeof payload !== "object") {
        return;
      }
      if ((payload as { type?: string }).type !== "mascarade-oauth-result") {
        return;
      }
      const provider = (payload as { provider?: string }).provider;
      if (provider !== "notion") {
        return;
      }
      const ok = (payload as { ok?: boolean }).ok === true;
      const nextMessage =
        typeof (payload as { message?: string }).message === "string"
          ? (payload as { message?: string }).message!
          : ok
            ? "OAuth linked"
            : "OAuth failed";
      void onSaved();
      settle(ok ? "ok" : "error", nextMessage);
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [group.name, onSaved]);

  const settle = (nextState: SaveState, nextMessage: string) => {
    setSaveState(nextState);
    setMessage(nextMessage);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setSaveState("idle");
      setMessage("");
    }, 5000);
  };

  const syncAuthIfNeeded = useCallback(
    async (response: RuntimeSecretMutationResponse) => {
      const token = response.client_token || response.generated_value;
      if (!token) {
        return;
      }
      const ok = await login(token, isPersisted());
      if (!ok) {
        throw new Error("Rotation de la cle appliquee, mais re-authentification impossible");
      }
    },
    [login],
  );

  const save = async () => {
    const values: Record<string, string> = {};
    const visibleFields = group.fields.filter((field) => {
      if (!field.auth_modes?.length) {
        return true;
      }
      return !!selectedAuthMode && field.auth_modes.includes(selectedAuthMode);
    });
    for (const field of visibleFields) {
      const value = drafts[field.env];
      if (value !== undefined && value !== "") {
        values[field.env] = value;
      }
    }
    if (group.auth_mode_env && drafts[group.auth_mode_env] !== undefined) {
      values[group.auth_mode_env] = drafts[group.auth_mode_env];
    }

    if (Object.keys(values).length === 0) {
      settle("error", "Aucune valeur a sauvegarder");
      return;
    }

    setSaveState("saving");
    try {
      const response = await put<RuntimeSecretMutationResponse>(
        `/api/settings/runtime-secrets/${group.name}`,
        { values },
      );
      if (group.name === "auth") {
        await syncAuthIfNeeded(response);
      }
      setDrafts({});
      setGeneratedValue("");
      setExtraInfo("");
      await onSaved();
      settle(
        "ok",
        response.restarted_services?.length
          ? `Sauvegarde appliquee, restart: ${response.restarted_services.join(", ")}`
          : response.message || "Sauvegarde appliquee",
      );
    } catch (error) {
      settle("error", error instanceof Error ? error.message : "Erreur");
    }
  };

  const clearGroup = async () => {
    setSaveState("saving");
    try {
      const response = await post<RuntimeSecretMutationResponse>(
        `/api/settings/runtime-secrets/${group.name}/clear`,
      );
      if (group.name === "auth") {
        logout();
      }
      setDrafts({});
      setGeneratedValue("");
      setExtraInfo("");
      await onSaved();
      settle(
        "ok",
        response.restarted_services?.length
          ? `Valeurs effacees, restart: ${response.restarted_services.join(", ")}`
          : response.message || "Valeurs effacees",
      );
    } catch (error) {
      settle("error", error instanceof Error ? error.message : "Erreur");
    }
  };

  const generate = async () => {
    setSaveState("saving");
    try {
      const response = await post<RuntimeSecretMutationResponse>(
        `/api/settings/runtime-secrets/${group.name}/generate`,
      );
      await syncAuthIfNeeded(response);
      setGeneratedValue(response.generated_value || "");
      setDrafts({});
      setExtraInfo("");
      await onSaved();
      settle(
        "ok",
        response.restarted_services?.length
          ? `Nouvelle cle generee, restart: ${response.restarted_services.join(", ")}`
          : response.message || "Nouvelle cle generee",
      );
    } catch (error) {
      settle("error", error instanceof Error ? error.message : "Erreur");
    }
  };

  const connectNotionOAuth = () => {
    const popup = window.open(
      "/api/settings/runtime-secrets/notion/oauth/start",
      "mascarade-notion-oauth",
      "popup=yes,width=720,height=820",
    );
    if (!popup) {
      settle("error", "Popup bloquee");
      return;
    }
    settle("ok", "OAuth Notion en cours...");
  };

  const validateGitHubApp = async () => {
    setSaveState("saving");
    try {
      const response = await post<{ status: string; expires_at?: string }>(
        "/api/settings/runtime-secrets/github-dispatch/app-token",
      );
      setExtraInfo(response.expires_at ? `installation token expires ${response.expires_at}` : "");
      settle("ok", "GitHub App valide");
    } catch (error) {
      settle("error", error instanceof Error ? error.message : "Erreur");
    }
  };

  const visibleFields = group.fields.filter((field) => {
    if (!field.auth_modes?.length) {
      return true;
    }
    return !!selectedAuthMode && field.auth_modes.includes(selectedAuthMode);
  });

  const hasDraft =
    visibleFields.some((field) => (drafts[field.env] || "").trim().length > 0) ||
    (!!group.auth_mode_env && drafts[group.auth_mode_env] !== undefined);

  return (
    <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold uppercase tracking-[0.18em] text-accent">
            {group.label}
          </p>
          <p className="mt-1 text-[12px] leading-5 text-amber-100/48">
            {group.description}
          </p>
          <MetaLine
            criticality={group.criticality}
            classification={group.classification}
            requiredWhen={group.required_when}
            usedBy={group.used_by}
          />
        </div>
        <RuntimeBadge
          configured={group.configured}
          configuredCount={group.configured_count}
          fieldCount={group.field_count}
        />
      </div>

      <div className="space-y-3">
        {group.auth_mode_env && group.auth_modes && group.auth_modes.length > 1 && (
          <div>
            <label className="mb-1.5 flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-muted">
              <span>Auth mode</span>
              <span className="normal-case tracking-normal text-amber-100/35">
                {group.auth_mode_env}
              </span>
            </label>
            <select
              value={selectedAuthMode ?? group.auth_modes[0]}
              onChange={(e) => setField(group.auth_mode_env!, e.target.value)}
              className="w-full rounded-2xl border border-border/80 bg-black/35 px-3 py-2.5 text-sm text-amber-100 outline-none transition focus:border-accent/50"
            >
              {group.auth_modes.map((mode) => (
                <option key={mode} value={mode} className="bg-[#0a0a0a]">
                  {mode}
                </option>
              ))}
            </select>
          </div>
        )}

        {visibleFields.map((field) => (
          <div key={field.env}>
            <label className="mb-1.5 flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-muted">
              <span>{field.label}</span>
              <span className="flex items-center gap-2">
                {field.criticality && field.criticality !== group.criticality && (
                  <CriticalityChip level={field.criticality} />
                )}
                <span className="normal-case tracking-normal text-amber-100/35">
                  {field.env}
                </span>
              </span>
            </label>
            <input
              type={field.secret ? "password" : "text"}
              placeholder={field.configured ? field.hint : "Non configure"}
              value={drafts[field.env] ?? ""}
              onChange={(e) => setField(field.env, e.target.value)}
              className="w-full rounded-2xl border border-border/80 bg-black/35 px-3 py-2.5 text-sm text-amber-100 outline-none transition placeholder:text-amber-100/25 focus:border-accent/50"
            />
            {field.restart_services.length > 0 && (
              <p className="mt-1 text-[11px] text-amber-100/35">
                restart: {field.restart_services.join(", ")}
              </p>
            )}
          </div>
        ))}
      </div>

      {generatedValue && (
        <div className="mt-4 rounded-2xl border border-[#214e31] bg-[#0c170f]/80 p-3">
          <p className="text-[11px] uppercase tracking-[0.16em] text-[#8cffb7]">
            generated value
          </p>
          <code className="mt-2 block overflow-x-auto whitespace-pre-wrap break-all text-[12px] text-[#c9ffd8]">
            {generatedValue}
          </code>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          {message && (
            <p
              className={[
                "text-[12px]",
                saveState === "ok" ? "text-emerald-400" : "text-red-400",
              ].join(" ")}
            >
              {message}
            </p>
          )}
          {extraInfo && (
            <p className="text-[11px] text-amber-100/35">
              {extraInfo}
            </p>
          )}
          {group.restart_services.length > 0 && (
            <p className="text-[11px] text-amber-100/35">
              redemarrage pilote: {group.restart_services.join(", ")}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {group.name === "notion" && selectedAuthMode === "oauth_oidc" && (
            <button
              type="button"
              disabled={saveState === "saving"}
              onClick={connectNotionOAuth}
              className="rounded-2xl border border-[#214e31] bg-[#0c170f]/80 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-[#8cffb7] transition hover:border-[#2d6942] hover:bg-[#0f2116] disabled:cursor-not-allowed disabled:opacity-40"
            >
              connect
            </button>
          )}
          {group.name === "github-dispatch" && selectedAuthMode === "app" && (
            <button
              type="button"
              disabled={saveState === "saving" || hasDraft}
              onClick={validateGitHubApp}
              className="rounded-2xl border border-[#214e31] bg-[#0c170f]/80 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-[#8cffb7] transition hover:border-[#2d6942] hover:bg-[#0f2116] disabled:cursor-not-allowed disabled:opacity-40"
            >
              validate app
            </button>
          )}
          {group.generate_supported && (
            <button
              type="button"
              disabled={saveState === "saving"}
              onClick={generate}
              className="rounded-2xl border border-[#214e31] bg-[#0c170f]/80 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-[#8cffb7] transition hover:border-[#2d6942] hover:bg-[#0f2116] disabled:cursor-not-allowed disabled:opacity-40"
            >
              generate
            </button>
          )}
          <button
            type="button"
            disabled={saveState === "saving" || !group.configured}
            onClick={clearGroup}
            className="rounded-2xl border border-red-800/50 bg-red-900/10 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-red-300 transition hover:border-red-700/60 hover:bg-red-900/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            clear
          </button>
          <button
            type="button"
            disabled={!hasDraft || saveState === "saving"}
            onClick={save}
            className="rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-accent transition hover:border-accent/50 hover:bg-accent/18 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saveState === "saving" ? "..." : "save"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Settings() {
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [runtimeGroups, setRuntimeGroups] = useState<RuntimeSecretGroupStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const [providerResponse, runtimeResponse] = await Promise.all([
        get<{ providers: ProviderStatus[] }>("/api/agents/providers/status"),
        get<{ groups: RuntimeSecretGroupStatus[] }>("/api/settings/runtime-secrets"),
      ]);
      setProviders(providerResponse.providers);
      setRuntimeGroups(runtimeResponse.groups);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchStatus();
  }, [fetchStatus]);

  const active = providers.filter((p) => p.active);
  const inactive = providers.filter((p) => !p.active);
  const runtimeReady = runtimeGroups.filter((group) => group.configured);
  const runtimeMissing = runtimeGroups.filter((group) => !group.configured);
  const runtimeSecurityGroups = runtimeGroups.filter((group) => group.criticality === "required-security");
  const runtimeIntegrationGroups = runtimeGroups.filter((group) => group.criticality !== "required-security");

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-[1.4rem] border border-accent/18 bg-accent/5 p-5">
          <p className="screen-label">provider administration</p>
          <p className="mt-2 text-[12px] leading-5 text-amber-100/58">
            Configuration des cles API pour chaque provider LLM. Les cles sont
            stockees cote serveur et ne sont jamais exposees au navigateur. Seul un
            indice masque est affiche pour les cles deja configurees.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">
              {active.length} actif{active.length > 1 ? "s" : ""}
            </span>
            <span className="status-chip border-border/80 bg-black/25 text-muted">
              {inactive.length} non configure{inactive.length > 1 ? "s" : ""}
            </span>
          </div>
        </div>

        <div className="rounded-[1.4rem] border border-accent/18 bg-accent/5 p-5">
          <p className="screen-label">runtime security + integrations</p>
          <p className="mt-2 text-[12px] leading-5 text-amber-100/58">
            `MASCARADE_API_KEY` reste une exigence de securite runtime distincte des
            integrations optionnelles. Les changements ecrivent le `.env`, mettent a
            jour le runtime et redemarrent le `core` seulement quand c'est necessaire.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">
              {runtimeReady.length} configure{runtimeReady.length > 1 ? "s" : ""}
            </span>
            <span className="status-chip border-border/80 bg-black/25 text-muted">
              {runtimeMissing.length} incomplet{runtimeMissing.length > 1 ? "s" : ""}
            </span>
          </div>
        </div>
      </div>

      <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-5">
        <p className="screen-label">secret matrix</p>
        <p className="mt-2 text-[12px] leading-5 text-amber-100/52">
          Les secrets sont qualifies par criticite: securite runtime obligatoire,
          prerequis de feature, aides de validation live, ou simple contexte operateur.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <CriticalityChip level="required-security" />
          <CriticalityChip level="feature-required" />
          <CriticalityChip level="live-validation-optional" />
          <CriticalityChip level="local-operator-context" />
        </div>
      </div>

      {loading && (
        <p className="text-center text-sm text-muted">Chargement...</p>
      )}

      {error && (
        <div className="rounded-2xl border border-red-800/60 bg-red-900/15 p-4 text-[12px] text-red-400">
          {error}
        </div>
      )}

      {runtimeSecurityGroups.length > 0 && (
        <section>
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">
            Security runtime
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {runtimeSecurityGroups.map((group) => (
              <RuntimeSecretCard key={group.name} group={group} onSaved={fetchStatus} />
            ))}
          </div>
        </section>
      )}

      {runtimeIntegrationGroups.length > 0 && (
        <section>
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">
            Integrations runtime
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {runtimeIntegrationGroups.map((group) => (
              <RuntimeSecretCard key={group.name} group={group} onSaved={fetchStatus} />
            ))}
          </div>
        </section>
      )}

      {active.length > 0 && (
        <section>
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">
            Providers actifs
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {active.map((provider) => (
              <ProviderCard key={provider.name} provider={provider} onSaved={() => void fetchStatus()} />
            ))}
          </div>
        </section>
      )}

      {inactive.length > 0 && (
        <section>
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">
            Providers disponibles
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {inactive.map((provider) => (
              <ProviderCard key={provider.name} provider={provider} onSaved={() => void fetchStatus()} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

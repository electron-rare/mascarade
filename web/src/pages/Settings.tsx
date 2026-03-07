import { useCallback, useEffect, useRef, useState } from "react";
import { get, isPersisted, post, put } from "../api/client";
import { useAuth } from "../auth/AuthContext";

interface FieldStatus {
  env: string;
  label: string;
  configured: boolean;
  hint: string;
  secret: boolean;
  auth_modes?: string[];
}

interface ProviderStatus {
  name: string;
  label: string;
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

interface RuntimeSecretFieldStatus {
  env: string;
  label: string;
  configured: boolean;
  hint: string;
  secret: boolean;
  restart_services: string[];
}

interface RuntimeSecretGroupStatus {
  name: string;
  label: string;
  description: string;
  configured: boolean;
  configured_count: number;
  field_count: number;
  generate_supported: boolean;
  restart_services: string[];
  fields: RuntimeSecretFieldStatus[];
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
  onSaved: () => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [message, setMessage] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const selectedAuthMode =
    provider.auth_mode_env && drafts[provider.auth_mode_env] !== undefined
      ? drafts[provider.auth_mode_env]
      : provider.auth_mode;

  const setField = (env: string, value: string) => {
    setDrafts((prev) => ({ ...prev, [env]: value }));
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
      const res = await put<{ status: string; active: boolean; message?: string }>(
        `/api/agents/providers/${provider.name}/key`,
        { keys },
      );
      setSaveState("ok");
      setMessage(res.active ? "Provider actif" : res.message || "Sauvegarde mais pas actif");
      setDrafts({});
      onSaved();
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

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  const visibleFields = provider.fields.filter((field) => {
    if (!field.auth_modes?.length) {
      return true;
    }
    return !!selectedAuthMode && field.auth_modes.includes(selectedAuthMode);
  });
  const hasDraft = visibleFields.some((field) => drafts[field.env]?.trim()) ||
    (!!provider.auth_mode_env && drafts[provider.auth_mode_env] !== undefined) ||
    (!!provider.toggle_env && drafts[provider.toggle_env] !== undefined);

  return (
    <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold uppercase tracking-[0.18em] text-accent">
            {provider.label}
          </p>
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
              <span className="normal-case tracking-normal text-amber-100/35">
                {field.env}
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
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const setField = (env: string, value: string) => {
    setDrafts((prev) => ({ ...prev, [env]: value }));
    setSaveState("idle");
    setMessage("");
  };

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

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
    for (const field of group.fields) {
      const value = drafts[field.env];
      if (value !== undefined && value !== "") {
        values[field.env] = value;
      }
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

  const hasDraft = group.fields.some((field) => (drafts[field.env] || "").trim().length > 0);

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
        </div>
        <RuntimeBadge
          configured={group.configured}
          configuredCount={group.configured_count}
          fieldCount={group.field_count}
        />
      </div>

      <div className="space-y-3">
        {group.fields.map((field) => (
          <div key={field.env}>
            <label className="mb-1.5 flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-muted">
              <span>{field.label}</span>
              <span className="normal-case tracking-normal text-amber-100/35">
                {field.env}
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
          {group.restart_services.length > 0 && (
            <p className="text-[11px] text-amber-100/35">
              redemarrage pilote: {group.restart_services.join(", ")}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
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
          <p className="screen-label">integrations / auth</p>
          <p className="mt-2 text-[12px] leading-5 text-amber-100/58">
            Edition directe des secrets runtime utilises par les MCP et l'auth locale.
            Les changements ecrivent le `.env`, mettent a jour le runtime et
            redemarrent le `core` seulement quand c'est necessaire.
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

      {loading && (
        <p className="text-center text-sm text-muted">Chargement...</p>
      )}

      {error && (
        <div className="rounded-2xl border border-red-800/60 bg-red-900/15 p-4 text-[12px] text-red-400">
          {error}
        </div>
      )}

      {runtimeGroups.length > 0 && (
        <section>
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">
            Integrations et auth runtime
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {runtimeGroups.map((group) => (
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

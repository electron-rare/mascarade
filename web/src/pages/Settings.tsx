import { useCallback, useEffect, useRef, useState } from "react";
import { get, put } from "../api/client";

interface FieldStatus {
  env: string;
  label: string;
  configured: boolean;
  hint: string;
  secret: boolean;
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

  const setField = (env: string, value: string) => {
    setDrafts((prev) => ({ ...prev, [env]: value }));
    setSaveState("idle");
    setMessage("");
  };

  const save = async () => {
    const keys: Record<string, string> = {};
    for (const field of provider.fields) {
      const val = drafts[field.env];
      if (val !== undefined && val !== "") {
        keys[field.env] = val;
      }
    }
    if (provider.toggle_env && drafts[provider.toggle_env] !== undefined) {
      keys[provider.toggle_env] = drafts[provider.toggle_env];
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

  const hasDraft = provider.fields.some((f) => drafts[f.env]?.trim());

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
        {provider.fields.map((field) => (
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
          disabled={!hasDraft && !Object.keys(drafts).length || saveState === "saving"}
          onClick={save}
          className="rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-accent transition hover:border-accent/50 hover:bg-accent/18 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saveState === "saving" ? "..." : "save"}
        </button>
      </div>
    </div>
  );
}

export default function Settings() {
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const res = await get<{ providers: ProviderStatus[] }>(
        "/api/agents/providers/status",
      );
      setProviders(res.providers);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const active = providers.filter((p) => p.active);
  const inactive = providers.filter((p) => !p.active);

  return (
    <div className="mx-auto max-w-4xl space-y-8">
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

      {loading && (
        <p className="text-center text-sm text-muted">Chargement...</p>
      )}

      {error && (
        <div className="rounded-2xl border border-red-800/60 bg-red-900/15 p-4 text-[12px] text-red-400">
          {error}
        </div>
      )}

      {active.length > 0 && (
        <section>
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">
            Providers actifs
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {active.map((p) => (
              <ProviderCard key={p.name} provider={p} onSaved={fetchStatus} />
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
            {inactive.map((p) => (
              <ProviderCard key={p.name} provider={p} onSaved={fetchStatus} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

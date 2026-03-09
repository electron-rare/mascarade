import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import Button from "../components/ui/Button";
import Spinner from "../components/ui/Spinner";
import { useAuth } from "./AuthContext";

export default function AuthGate({ children }: { children: ReactNode }) {
  const { authRequired, authenticated, checking, login } = useAuth();

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="space-y-4 text-center">
          <Spinner className="mx-auto h-10 w-10" />
          <p className="screen-label justify-center">initializing gateway</p>
        </div>
      </div>
    );
  }

  if (!authRequired || authenticated) {
    return <>{children}</>;
  }

  return <LoginOverlay onLogin={login} />;
}

function LoginOverlay({
  onLogin,
}: {
  onLogin: (key: string, persist: boolean) => Promise<boolean>;
}) {
  const [key, setKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [persist, setPersist] = useState(false);
  const [status, setStatus] = useState<"idle" | "checking" | "invalid">("idle");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = key.trim();
    if (!trimmed) return;
    setStatus("checking");
    const valid = await onLogin(trimmed, persist);
    if (!valid) setStatus("invalid");
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md rounded-[1.75rem] border border-border/80 bg-[linear-gradient(180deg,rgba(8,9,8,0.94),rgba(6,6,6,0.98))] p-8 shadow-[0_24px_80px_rgba(0,0,0,0.55)]">
        <div className="space-y-6">
          <div className="space-y-2 text-center">
            <p className="screen-label justify-center">gateway auth</p>
            <h1 className="text-2xl font-semibold uppercase tracking-[0.18em] text-accent glow-text">
              Mascarade
            </h1>
            <p className="text-sm leading-6 text-amber-100/58">
              Entrez votre cle API pour acceder au cockpit.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-2 block text-[11px] uppercase tracking-[0.18em] text-muted">
                API Key
              </label>
              <div className="flex gap-2">
                <input
                  ref={inputRef}
                  type={showKey ? "text" : "password"}
                  value={key}
                  onChange={(e) => {
                    setKey(e.target.value);
                    setStatus("idle");
                  }}
                  className="min-w-0 flex-1 rounded-2xl border border-border/80 bg-black/35 px-3 py-3 text-sm text-amber-100 outline-none transition focus:border-accent/50"
                  placeholder="Enter your API key"
                  autoComplete="off"
                />
                <Button
                  variant="ghost"
                  type="button"
                  className="px-3"
                  onClick={() => setShowKey((c) => !c)}
                >
                  {showKey ? "hide" : "show"}
                </Button>
              </div>
            </div>

            {status === "invalid" && (
              <p className="text-[12px] text-red-400">
                Cle invalide — verifiez le token ou la connectivite API.
              </p>
            )}

            <label className="flex cursor-pointer items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted">
              <input
                type="checkbox"
                checked={persist}
                onChange={(e) => setPersist(e.target.checked)}
                className="accent-accent"
              />
              Retenir 30 jours
            </label>

            <Button
              type="submit"
              className="w-full"
              loading={status === "checking"}
              disabled={!key.trim()}
            >
              {status === "checking" ? "verification..." : "connect"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { getApiKey, setApiKey, api } from "../../api/client";

interface HealthData {
  status: string;
  core?: { status: string };
}

type TopBarProps = {
  eyebrow: string;
  title: string;
  description: string;
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
  navOpen,
  onMenuToggle,
}: TopBarProps) {
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState(getApiKey);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [clockLabel, setClockLabel] = useState(() =>
    new Intl.DateTimeFormat("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date()),
  );
  const ref = useRef<HTMLDivElement>(null);
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

  const save = () => {
    setApiKey(key.trim());
    setOpen(false);
  };

  const apiOk = health?.status === "ok";
  const coreOk = health?.core?.status === "ok";
  const authReady = key.trim().length > 0;

  return (
    <header className="sticky top-0 z-20 border-b border-border/80 bg-[linear-gradient(180deg,rgba(7,9,8,0.88),rgba(7,8,7,0.72))] px-4 py-4 backdrop-blur-xl md:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onMenuToggle}
              className="flex h-10 w-10 items-center justify-center rounded-2xl border border-border/80 bg-black/30 text-sm text-accent transition hover:border-accent/45 hover:bg-accent/10 lg:hidden"
              aria-label={navOpen ? "Close navigation" : "Open navigation"}
            >
              {navOpen ? "✕" : "☰"}
            </button>
            <span className="screen-label">{eyebrow}</span>
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
              className="flex h-10 items-center gap-2 rounded-2xl border border-border/80 bg-black/30 px-3 text-xs uppercase tracking-[0.18em] text-amber-100/74 transition hover:border-accent/45 hover:text-accent"
              title="API Key"
            >
              <span className="text-sm">🔑</span>
              auth key
            </button>
            {open && (
              <div className="absolute right-0 top-14 z-50 w-[21rem] rounded-3xl border border-border/80 bg-[linear-gradient(180deg,rgba(7,7,7,0.98),rgba(10,11,10,0.96))] p-4 shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
                <div className="mb-4 space-y-1">
                  <p className="screen-label">gateway auth</p>
                  <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-accent">
                    Bearer token
                  </h3>
                  <p className="text-[12px] leading-5 text-amber-100/50">
                    Cle locale stockee en cookie pour appeler l'API Mascarade depuis le cockpit.
                  </p>
                </div>
                <label className="mb-2 block text-[11px] uppercase tracking-[0.18em] text-muted">
                  API Key
                </label>
                <input
                  type="password"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  className="w-full rounded-2xl border border-border/80 bg-black/35 px-3 py-3 text-sm text-amber-100 outline-none transition focus:border-accent/50"
                  placeholder="Enter your API key"
                />
                <div className="mt-4 flex items-center justify-between gap-3">
                  <span className="text-[11px] uppercase tracking-[0.16em] text-amber-100/40">
                    {authReady ? "key present" : "no key loaded"}
                  </span>
                  <button
                    type="button"
                    onClick={save}
                    className="rounded-2xl border border-accent/40 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
                  >
                    save
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

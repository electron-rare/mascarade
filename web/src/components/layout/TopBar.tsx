import { useState, useRef, useEffect } from "react";
import { getApiKey, setApiKey } from "../../api/client";
import { useFetch } from "../../hooks/useFetch";

export default function TopBar({ title }: { title: string }) {
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState(getApiKey);
  const ref = useRef<HTMLDivElement>(null);
  const { data: health, refetch } = useFetch<{
    status: string;
    core?: { status: string };
  }>("/health");

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node))
        setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    const t = window.setInterval(() => {
      refetch();
    }, 5000);
    return () => window.clearInterval(t);
  }, [refetch]);

  const save = () => {
    setApiKey(key);
    setOpen(false);
  };

  const apiStatus = health?.status === "ok" ? "OK" : "DOWN";
  const coreStatus = health?.core?.status === "ok" ? "OK" : "DOWN";

  return (
    <header className="h-12 border-b border-border flex items-center justify-between px-5 bg-surface/95 backdrop-blur shrink-0 shadow-[0_0_14px_rgba(27,77,44,0.25)]">
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-xs text-muted hidden md:inline uppercase tracking-[0.14em]">sys_monitor</span>
        <span className="text-xs text-accent hidden md:inline uppercase tracking-[0.14em]">--live</span>
        <span className="text-xs text-muted hidden md:inline">|</span>
        <span className="text-xs text-muted hidden md:inline uppercase">API:</span>
        <span
          className={`text-xs hidden md:inline ${apiStatus === "OK" ? "text-accent" : "text-error"}`}
        >
          {apiStatus}
        </span>
        <span className="text-xs text-muted hidden md:inline uppercase">CORE:</span>
        <span
          className={`text-xs hidden md:inline ${coreStatus === "OK" ? "text-accent" : "text-error"}`}
        >
          {coreStatus}
        </span>
        <h1 className="text-xs font-semibold text-accent truncate uppercase tracking-[0.14em]">{title}</h1>
      </div>
      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen(!open)}
          className="text-muted hover:text-accent transition-colors text-sm border border-border rounded px-1.5 py-0.5 bg-black/30"
          title="API Key"
        >
          🔑
        </button>
        {open && (
          <div className="absolute right-0 top-10 bg-surface border border-border rounded-md p-3 shadow-xl z-50 w-72">
            <label className="text-xs text-muted block mb-1 uppercase tracking-wide">API Key</label>
            <input
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              className="w-full bg-bg border border-border rounded px-2 py-1.5 text-sm text-amber-100 outline-none focus:border-accent"
              placeholder="Enter your API key"
            />
            <button
              onClick={save}
              className="mt-2 w-full bg-accent text-black text-sm font-semibold py-1.5 rounded hover:bg-[#ffdc86] transition-colors uppercase tracking-wide"
            >
              Save
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

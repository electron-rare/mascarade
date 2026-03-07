import { NavLink } from "react-router-dom";
import { getDifyOrigin } from "../../lib/dify";
import { navigationGroups, navigationItems, resolvePage } from "./navigation";

type SidebarProps = {
  pathname: string;
  open: boolean;
  onClose: () => void;
};

export default function Sidebar({ pathname, open, onClose }: SidebarProps) {
  const page = resolvePage(pathname);
  const host = window.location.host;
  const difyHref = `${getDifyOrigin()}/`;

  return (
    <aside
      id="primary-sidebar"
      className={[
        "fixed inset-y-0 left-0 z-40 flex w-[18rem] flex-col border-r border-border/80",
        "bg-[linear-gradient(180deg,rgba(5,9,7,0.96),rgba(4,4,4,0.94))] shadow-[0_0_40px_rgba(0,0,0,0.55)] backdrop-blur-xl",
        "transition-transform duration-300 ease-out lg:static lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full",
      ].join(" ")}
    >
      <div className="border-b border-border/80 px-5 pb-4 pt-5">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="screen-label text-[10px] uppercase">mascarade / ops</p>
            <h2 className="mt-2 text-lg font-semibold uppercase tracking-[0.28em] text-accent glow-text">
              cockpit
            </h2>
            <p className="mt-2 max-w-[16rem] text-[11px] leading-5 text-amber-100/58">
              Interface de supervision locale pour la gateway, les agents et les integrations relies au core.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border/80 bg-black/30 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-muted transition hover:border-accent/40 hover:text-accent lg:hidden"
          >
            close
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[11px] uppercase tracking-[0.16em]">
          <div className="rounded-2xl border border-border/70 bg-black/25 px-3 py-2">
            <span className="text-muted">mode</span>
            <p className="mt-1 text-accent">local stack</p>
          </div>
          <div className="rounded-2xl border border-border/70 bg-black/25 px-3 py-2">
            <span className="text-muted">theme</span>
            <p className="mt-1 glow-green">crt active</p>
          </div>
        </div>

        <div className="mt-3 rounded-[1.6rem] border border-accent/18 bg-accent/5 p-4">
          <p className="screen-label">current lane</p>
          <div className="mt-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-accent">
                {page.title}
              </p>
              <p className="mt-2 text-[11px] leading-5 text-amber-100/52">{page.description}</p>
            </div>
            <span className="status-chip border-accent/28 bg-accent/8 px-3 py-2 text-accent">
              {page.index}
            </span>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] uppercase tracking-[0.16em]">
          <NavLink
            to="/agents/agent-zero"
            className="rounded-2xl border border-accent/28 bg-accent/8 px-3 py-3 text-center text-accent transition hover:border-accent/45 hover:bg-accent/12"
          >
            agent zero
          </NavLink>
          <a
            href={difyHref}
            target="_blank"
            rel="noreferrer"
            className="rounded-2xl border border-border/70 bg-black/25 px-3 py-3 text-center text-amber-100/70 transition hover:border-accent/35 hover:text-accent"
          >
            dify
          </a>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <div className="space-y-5">
          {navigationGroups.map((group) => (
            <section key={group.label}>
              <div className="mb-2 flex items-center justify-between px-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-muted">
                  {group.label}
                </p>
                <span className="text-[10px] uppercase tracking-[0.16em] text-amber-100/35">
                  {group.items.length.toString().padStart(2, "0")}
                </span>
              </div>
              <div className="space-y-1.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      [
                        "group block rounded-2xl border px-3 py-3 transition-all duration-200",
                        isActive
                          ? "border-accent/40 bg-accent/10 shadow-[0_0_18px_rgba(255,209,102,0.12)]"
                          : "border-transparent bg-white/[0.015] hover:border-border/80 hover:bg-white/[0.04]",
                      ].join(" ")
                    }
                  >
                    {({ isActive }) => (
                      <div className="flex items-start gap-3">
                        <span
                          className={[
                            "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border text-sm transition-colors",
                            isActive
                              ? "border-accent/50 bg-accent/10 text-accent"
                              : "border-border/70 bg-black/30 text-amber-100/75 group-hover:text-accent",
                          ].join(" ")}
                        >
                          {item.icon}
                        </span>
                        <div className="min-w-0">
                          <p
                            className={[
                              "text-[12px] font-semibold uppercase tracking-[0.18em] transition-colors",
                              isActive ? "text-accent glow-text" : "text-amber-100/88 group-hover:text-accent",
                            ].join(" ")}
                          >
                            {item.label}
                          </p>
                          <p className="mt-1 text-[11px] leading-5 text-amber-100/45">{item.hint}</p>
                        </div>
                      </div>
                    )}
                  </NavLink>
                ))}
              </div>
            </section>
          ))}
        </div>
      </nav>

      <div className="border-t border-border/80 px-4 py-4 text-[11px] text-amber-100/48">
        <div className="space-y-3">
          <div className="rounded-2xl border border-border/70 bg-black/25 px-3 py-3">
            <p className="screen-label">gateway posture</p>
            <p className="mt-2 text-[12px] leading-5 text-amber-100/68">
              API locale en facade. Core, agents et integrations relies via la gateway interne.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px] uppercase tracking-[0.16em]">
            <a
              href="/ops"
              className="rounded-2xl border border-border/70 bg-black/25 px-3 py-3 text-center text-amber-100/70 transition hover:border-accent/35 hover:text-accent"
            >
              ops
            </a>
            <a
              href="/health"
              target="_blank"
              rel="noreferrer"
              className="rounded-2xl border border-border/70 bg-black/25 px-3 py-3 text-center text-amber-100/70 transition hover:border-accent/35 hover:text-accent"
            >
              api
            </a>
          </div>

          <div className="rounded-2xl border border-border/70 bg-black/25 px-3 py-3">
            <p className="text-[10px] uppercase tracking-[0.22em] text-muted">nav registry</p>
            <p className="mt-2 text-[12px] leading-5 text-amber-100/68">
              {navigationItems.length} lanes actives sur {host}.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}

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
        "fixed inset-y-0 left-0 z-40 flex w-[18rem] flex-col border-r border-[rgba(0,0,0,0.06)]",
        "bg-[rgba(255,255,255,0.92)] shadow-[0_2px_20px_rgba(0,0,0,0.06)] backdrop-blur-xl",
        "transition-transform duration-300 ease-out lg:static lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full",
      ].join(" ")}
    >
      <div className="border-b border-[rgba(0,0,0,0.06)] px-5 pb-4 pt-5">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[#86868b]">mascarade / ops</p>
            <h2 className="mt-2 text-lg font-semibold uppercase tracking-[0.28em] text-[#1d1d1f]">
              cockpit
            </h2>
            <p className="mt-2 max-w-[16rem] text-[11px] leading-5 text-[#86868b]">
              Interface de supervision locale pour la gateway, les agents et les integrations relies au core.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-[#86868b] transition hover:bg-[#e8e8ed] hover:text-[#1d1d1f] lg:hidden"
          >
            close
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[11px] uppercase tracking-[0.16em]">
          <div className="rounded-xl border border-[rgba(0,0,0,0.06)] bg-[#f5f5f7] px-3 py-2">
            <span className="text-[#86868b]">mode</span>
            <p className="mt-1 text-accent">local stack</p>
          </div>
          <div className="rounded-xl border border-[rgba(0,0,0,0.06)] bg-[#f5f5f7] px-3 py-2">
            <span className="text-[#86868b]">theme</span>
            <p className="mt-1 text-[#1d1d1f]">active</p>
          </div>
        </div>

        <div className="mt-3 rounded-xl border border-accent/12 bg-accent/4 p-4">
          <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[#86868b]">current lane</p>
          <div className="mt-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-accent">
                {page.title}
              </p>
              <p className="mt-2 text-[11px] leading-5 text-[#86868b]">{page.description}</p>
            </div>
            <span className="rounded-full border border-accent/20 bg-accent/8 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-accent">
              {page.index}
            </span>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] uppercase tracking-[0.16em]">
          <NavLink
            to="/agents/agent-zero"
            className="rounded-xl border border-accent/20 bg-accent/8 px-3 py-3 text-center text-accent transition hover:bg-accent/12"
          >
            agent zero
          </NavLink>
          <a
            href={difyHref}
            target="_blank"
            rel="noreferrer"
            className="rounded-xl border border-[rgba(0,0,0,0.06)] bg-[#f5f5f7] px-3 py-3 text-center text-[#6e6e73] transition hover:bg-[#e8e8ed] hover:text-accent"
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
                <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#86868b]">
                  {group.label}
                </p>
                <span className="text-[10px] uppercase tracking-[0.16em] text-[#86868b]/50">
                  {group.items.length.toString().padStart(2, "0")}
                </span>
              </div>
              <div className="space-y-1">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      [
                        "group block rounded-xl border px-3 py-3 transition-all duration-200",
                        isActive
                          ? "border-transparent bg-accent/8 text-accent shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                          : "border-transparent hover:bg-[#f5f5f7]",
                      ].join(" ")
                    }
                  >
                    {({ isActive }) => (
                      <div className="flex items-start gap-3">
                        <span
                          className={[
                            "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-sm transition-colors",
                            isActive
                              ? "border-accent/20 bg-accent/10 text-accent"
                              : "border-[rgba(0,0,0,0.06)] bg-[#f5f5f7] text-[#6e6e73] group-hover:text-accent",
                          ].join(" ")}
                        >
                          {item.icon}
                        </span>
                        <div className="min-w-0">
                          <p
                            className={[
                              "text-[12px] font-semibold uppercase tracking-[0.18em] transition-colors",
                              isActive ? "text-accent" : "text-[#1d1d1f] group-hover:text-accent",
                            ].join(" ")}
                          >
                            {item.label}
                          </p>
                          <p className="mt-1 text-[11px] leading-5 text-[#86868b]">{item.hint}</p>
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

      <div className="border-t border-[rgba(0,0,0,0.06)] px-4 py-4 text-[11px] text-[#86868b]">
        <div className="space-y-3">
          <div className="rounded-xl border border-[rgba(0,0,0,0.06)] bg-[#f5f5f7] px-3 py-3">
            <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[#86868b]">gateway posture</p>
            <p className="mt-2 text-[12px] leading-5 text-[#6e6e73]">
              API locale en facade. Core, agents et integrations relies via la gateway interne.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px] uppercase tracking-[0.16em]">
            <a
              href="/ops"
              className="rounded-xl border border-[rgba(0,0,0,0.06)] bg-[#f5f5f7] px-3 py-3 text-center text-[#6e6e73] transition hover:bg-[#e8e8ed] hover:text-accent"
            >
              ops
            </a>
            <a
              href="/health"
              target="_blank"
              rel="noreferrer"
              className="rounded-xl border border-[rgba(0,0,0,0.06)] bg-[#f5f5f7] px-3 py-3 text-center text-[#6e6e73] transition hover:bg-[#e8e8ed] hover:text-accent"
            >
              api
            </a>
          </div>

          <div className="rounded-xl border border-[rgba(0,0,0,0.06)] bg-[#f5f5f7] px-3 py-3">
            <p className="text-[10px] uppercase tracking-[0.22em] text-[#86868b]">nav registry</p>
            <p className="mt-2 text-[12px] leading-5 text-[#6e6e73]">
              {navigationItems.length} lanes actives sur {host}.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}

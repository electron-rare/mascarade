import { NavLink } from "react-router-dom";

const groups = [
  {
    label: "System",
    items: [{ to: "/metrics", icon: "▣", label: "System Monitor" }],
  },
  {
    label: "LLM",
    items: [
      { to: "/", icon: "⌘", label: "Dashboard" },
      { to: "/playground", icon: "▶", label: "Playground" },
      { to: "/agents", icon: "◎", label: "Agents" },
      { to: "/orchestrate", icon: "⚙", label: "Orchestrate" },
    ],
  },
  {
    label: "Ops",
    items: [
      { to: "/infra", icon: "⬡", label: "Infrastructure" },
    ],
  },
  {
    label: "Tools",
    items: [
      { to: "/notion", icon: "▤", label: "Notion" },
      { to: "/comfyui", icon: "◲", label: "ComfyUI" },
    ],
  },
];

export default function Sidebar() {
  return (
    <aside className="w-52 h-screen bg-surface/95 border-r border-border flex flex-col shrink-0 shadow-[0_0_20px_rgba(0,0,0,0.45)]">
      <div className="px-4 py-5 border-b border-border bg-black/35">
        <span className="text-accent font-bold text-sm tracking-[0.22em] uppercase glow-text glitch">
          ops_console
        </span>
        <p className="text-[9px] text-green-500/60 mt-1 tracking-widest glow-green cursor-blink">sys.init</p>
      </div>
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        {groups.map((g) => (
          <div key={g.label}>
            <p className="px-2 mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted">
              {g.label}
            </p>
            {g.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-2 py-1.5 rounded text-xs uppercase tracking-wide transition-all duration-200 border ${
                    isActive
                      ? "bg-accent/10 text-accent border-accent/40 glow-text shadow-[0_0_10px_rgba(255,209,102,0.15)]"
                      : "text-amber-100/85 border-transparent hover:bg-white/5 hover:border-border hover:shadow-[0_0_8px_rgba(27,77,44,0.3)]"
                  }`
                }
              >
                <span className="w-5 text-center text-[11px]">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}

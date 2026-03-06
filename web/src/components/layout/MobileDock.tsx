import { NavLink } from "react-router-dom";
import { mobileDockItems } from "./navigation";

type MobileDockProps = {
  onMenuOpen: () => void;
};

export default function MobileDock({ onMenuOpen }: MobileDockProps) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border/80 bg-[linear-gradient(180deg,rgba(6,7,7,0.9),rgba(4,4,4,0.96))] px-3 pb-3 pt-2 backdrop-blur-xl lg:hidden">
      <div className="mx-auto grid max-w-[1440px] grid-cols-5 gap-2">
        {mobileDockItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              [
                "flex min-h-[4.25rem] flex-col items-center justify-center rounded-[1.4rem] border px-2 py-2 text-center transition",
                isActive
                  ? "border-accent/40 bg-accent/10 text-accent shadow-[0_0_18px_rgba(255,209,102,0.12)]"
                  : "border-border/70 bg-black/30 text-amber-100/70",
              ].join(" ")
            }
          >
            <span className="text-base">{item.icon}</span>
            <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em]">
              {item.shortLabel}
            </span>
          </NavLink>
        ))}

        <button
          type="button"
          onClick={onMenuOpen}
          aria-label="Open navigation menu"
          className="flex min-h-[4.25rem] flex-col items-center justify-center rounded-[1.4rem] border border-border/70 bg-black/30 px-2 py-2 text-center text-amber-100/70 transition hover:border-accent/35 hover:text-accent"
        >
          <span className="text-base">☰</span>
          <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em]">Menu</span>
        </button>
      </div>
    </div>
  );
}

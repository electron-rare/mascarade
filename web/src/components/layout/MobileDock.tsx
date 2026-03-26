import { NavLink } from "react-router-dom";
import { mobileDockItems } from "./navigation";

type MobileDockProps = {
  navOpen: boolean;
  onMenuOpen: () => void;
};

export default function MobileDock({ navOpen, onMenuOpen }: MobileDockProps) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-[rgba(0,0,0,0.06)] bg-[rgba(255,255,255,0.92)] px-3 pb-3 pt-2 backdrop-blur-xl lg:hidden">
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
                  ? "border-accent/20 bg-accent/8 text-accent shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                  : "border-transparent bg-[#f5f5f7] text-[#86868b]",
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
          aria-controls="primary-sidebar"
          aria-expanded={navOpen}
          className="flex min-h-[4.25rem] flex-col items-center justify-center rounded-[1.4rem] border border-transparent bg-[#f5f5f7] px-2 py-2 text-center text-[#86868b] transition hover:bg-[#e8e8ed] hover:text-accent"
        >
          <span className="text-base">☰</span>
          <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em]">Menu</span>
        </button>
      </div>
    </div>
  );
}

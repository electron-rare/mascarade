import { NavLink } from "react-router-dom";
import { mobileDockItems } from "./navigation";

type MobileDockProps = {
  navOpen: boolean;
  onMenuOpen: () => void;
};

export default function MobileDock({ navOpen, onMenuOpen }: MobileDockProps) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-[rgba(255,255,255,0.1)] bg-[rgba(13,16,20,0.82)] px-3 pb-3 pt-2 backdrop-blur-xl lg:hidden">
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
                  ? "border-[rgba(127,192,255,0.4)] bg-[rgba(127,192,255,0.15)] text-[#CDEAFF] shadow-[0_8px_18px_rgba(0,0,0,0.35)]"
                  : "border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.04)] text-[#95A0B5]",
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
          className="flex min-h-[4.25rem] flex-col items-center justify-center rounded-[1.4rem] border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.04)] px-2 py-2 text-center text-[#95A0B5] transition hover:bg-[rgba(255,255,255,0.08)] hover:text-[#CDEAFF]"
        >
          <span className="text-base">☰</span>
          <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em]">Menu</span>
        </button>
      </div>
    </div>
  );
}

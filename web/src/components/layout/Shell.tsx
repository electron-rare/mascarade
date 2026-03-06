import { useEffect, useMemo, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import MobileDock from "./MobileDock";
import { resolvePage } from "./navigation";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function Shell() {
  const { pathname } = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  const page = useMemo(() => resolvePage(pathname), [pathname]);

  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setNavOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="relative flex min-h-screen text-amber-50">
      {navOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-black/70 backdrop-blur-sm lg:hidden"
          onClick={() => setNavOpen(false)}
        />
      )}

      <Sidebar pathname={pathname} open={navOpen} onClose={() => setNavOpen(false)} />

      <div className="relative z-10 flex min-h-screen min-w-0 flex-1 flex-col">
        <TopBar
          eyebrow={page.eyebrow}
          title={page.title}
          description={page.description}
          section={page.section}
          index={page.index}
          navOpen={navOpen}
          onMenuToggle={() => setNavOpen((current) => !current)}
        />
        <main className="flex-1 overflow-y-auto px-4 pb-28 pt-4 md:px-6 md:pb-10 lg:px-8 lg:pb-8">
          <div className="mx-auto w-full max-w-[1440px]">
            <Outlet />
          </div>
        </main>
      </div>

      <MobileDock onMenuOpen={() => setNavOpen(true)} />
    </div>
  );
}

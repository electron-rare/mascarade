import { useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import MobileDock from "./MobileDock";
import { navigationItems, resolvePage } from "./navigation";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function Shell() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [navOpen, setNavOpen] = useState(false);
  const page = useMemo(() => resolvePage(pathname), [pathname]);

  const focusMainContent = () => {
    window.requestAnimationFrame(() => {
      document.getElementById("main-content")?.focus();
    });
  };

  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isTypingContext =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target?.isContentEditable;
      const shortcutsLocked =
        !!document.querySelector('[role="dialog"]') ||
        !!document.querySelector('[data-shortcuts-lock="true"]');

      if (event.key === "Escape") {
        setNavOpen(false);
        return;
      }

      if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || isTypingContext || shortcutsLocked) {
        return;
      }

      const index = Number.parseInt(event.key, 10);
      if (Number.isNaN(index)) {
        return;
      }

      const destination = navigationItems[index - 1];
      if (!destination) {
        return;
      }

      event.preventDefault();
      setNavOpen(false);
      navigate(destination.to);
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [navigate]);

  return (
    <div className="relative flex min-h-screen bg-white text-[#1d1d1f]">
      <a
        href="#main-content"
        onClick={focusMainContent}
        className="sr-only z-[70] rounded-xl border border-[rgba(0,0,0,0.08)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>

      {navOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-[#f5f5f7] backdrop-blur-sm lg:hidden"
          onClick={() => setNavOpen(false)}
        />
      )}

      <Sidebar pathname={pathname} open={navOpen} onClose={() => setNavOpen(false)} />

      <div className="relative z-10 flex min-h-screen min-w-0 flex-1 flex-col bg-white">
        <TopBar
          eyebrow={page.eyebrow}
          title={page.title}
          description={page.description}
          section={page.section}
          index={page.index}
          navOpen={navOpen}
          onMenuToggle={() => setNavOpen((current) => !current)}
        />
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-y-auto px-4 pb-28 pt-4 md:px-6 md:pb-10 lg:px-8 lg:pb-8"
        >
          <div className="mx-auto w-full max-w-[1440px]">
            <Outlet />
          </div>
        </main>
      </div>

      <MobileDock navOpen={navOpen} onMenuOpen={() => setNavOpen(true)} />
    </div>
  );
}

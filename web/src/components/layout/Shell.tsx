import { useEffect, useMemo, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

type PageMeta = {
  eyebrow: string;
  title: string;
  description: string;
};

const pageMeta: Record<string, PageMeta> = {
  "/": {
    eyebrow: "command deck",
    title: "Dashboard",
    description: "Vue d'ensemble de la passerelle, des providers et du plan d'action operateur.",
  },
  "/playground": {
    eyebrow: "runtime lab",
    title: "Playground",
    description: "Tester les prompts, inspecter les sorties et iterer sur le routage en direct.",
  },
  "/agents": {
    eyebrow: "agent registry",
    title: "Agents",
    description: "Inventaire des agents exposes par le core et acces rapide a leurs details.",
  },
  "/orchestrate": {
    eyebrow: "flow control",
    title: "Orchestrate",
    description: "Composer des runs multi-etapes et piloter l'orchestration depuis l'interface.",
  },
  "/metrics": {
    eyebrow: "ops monitor",
    title: "Metrics",
    description: "Latence, sante et disponibilite des briques critiques de la stack Mascarade.",
  },
  "/infra": {
    eyebrow: "stack map",
    title: "Infrastructure",
    description: "Endpoints exposes, providers declares et etat brut de l'infrastructure.",
  },
  "/notion": {
    eyebrow: "knowledge bus",
    title: "Notion Browser",
    description: "Navigation des ressources Notion branchees sur la gateway Mascarade.",
  },
  "/comfyui": {
    eyebrow: "image lane",
    title: "ComfyUI",
    description: "Pilotage des workflows ComfyUI et verification rapide du pipeline image.",
  },
};

function resolvePage(pathname: string): PageMeta {
  if (pathname.startsWith("/agents/")) {
    const agent = pathname.split("/").pop() || "unknown";
    return {
      eyebrow: "agent focus",
      title: `Agent ${agent}`,
      description: "Configuration, capacites et introspection detaillee de l'agent selectionne.",
    };
  }

  return (
    pageMeta[pathname] || {
      eyebrow: "mascarade",
      title: "Mascarade",
      description: "Cockpit operateur pour la stack locale, les agents et les integrations runtime.",
    }
  );
}

export default function Shell() {
  const { pathname } = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  const page = useMemo(() => resolvePage(pathname), [pathname]);

  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

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

      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />

      <div className="relative z-10 flex min-h-screen min-w-0 flex-1 flex-col">
        <TopBar
          eyebrow={page.eyebrow}
          title={page.title}
          description={page.description}
          navOpen={navOpen}
          onMenuToggle={() => setNavOpen((current) => !current)}
        />
        <main className="flex-1 overflow-y-auto px-4 pb-8 pt-4 md:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-[1440px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

export type PageMeta = {
  eyebrow: string;
  title: string;
  description: string;
  section: string;
  index: string;
};

export type NavItem = {
  to: string;
  icon: string;
  label: string;
  shortLabel: string;
  hint: string;
  eyebrow: string;
  title: string;
  description: string;
  section: string;
};

export type NavGroup = {
  label: string;
  items: NavItem[];
};

export const navigationGroups: NavGroup[] = [
  {
    label: "Core",
    items: [
      {
        to: "/",
        icon: "\u2318",
        label: "Dashboard",
        shortLabel: "Home",
        hint: "overview + launch lanes",
        eyebrow: "command deck",
        title: "Dashboard",
        description: "Vue d'ensemble de la passerelle, des providers et du plan d'action operateur.",
        section: "Core",
      },
      {
        to: "/playground",
        icon: "\u25B6",
        label: "Playground",
        shortLabel: "Lab",
        hint: "prompt sandbox",
        eyebrow: "runtime lab",
        title: "Playground",
        description: "Tester les prompts, inspecter les sorties et iterer sur le routage en direct.",
        section: "Core",
      },
      {
        to: "/agents",
        icon: "\u25CE",
        label: "Agents",
        shortLabel: "Agents",
        hint: "registry + detail",
        eyebrow: "agent registry",
        title: "Agents",
        description: "Inventaire des agents exposes par le core et acces rapide a leurs details.",
        section: "Core",
      },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        to: "/training",
        icon: "\u25A7",
        label: "Training",
        shortLabel: "Train",
        hint: "training + datasets + benchmark",
        eyebrow: "training deck",
        title: "Training",
        description: "Monitoring temps reel du training, datasets, benchmark et GPU telemetry.",
        section: "Operations",
      },
      {
        to: "/knowledge",
        icon: "\u25A4",
        label: "Knowledge",
        shortLabel: "KB",
        hint: "qdrant + semantic search",
        eyebrow: "knowledge base",
        title: "Knowledge",
        description: "Navigation des collections Qdrant, recherche semantique et gestion des documents.",
        section: "Operations",
      },
      {
        to: "/admin",
        icon: "\u2699",
        label: "Admin",
        shortLabel: "Admin",
        hint: "control + fleet + settings + mcp",
        eyebrow: "administration",
        title: "Administration",
        description: "Panneau de controle: services, fleet, settings, MCP servers, users et audit.",
        section: "Operations",
      },
    ],
  },
  {
    label: "Integrations",
    items: [
      {
        to: "/kill-life",
        icon: "\u25EB",
        label: "Kill_LIFE",
        shortLabel: "Workflow",
        hint: "graph editor",
        eyebrow: "embedded lane",
        title: "Kill_LIFE",
        description: "Editeur graphique de workflows embarques, validation locale et dispatch GitHub depuis le cockpit.",
        section: "Integrations",
      },
    ],
  },
];

export const navigationItems = navigationGroups.flatMap((group) => group.items);
export const mobileDockItems = navigationItems.filter((item) =>
  ["/", "/playground", "/agents", "/training"].includes(item.to),
);

function resolveBaseItem(pathname: string): NavItem | undefined {
  if (pathname.startsWith("/agents/")) {
    return navigationItems.find((item) => item.to === "/agents");
  }

  if (pathname.startsWith("/kill-life/")) {
    return navigationItems.find((item) => item.to === "/kill-life");
  }

  return navigationItems.find((item) => item.to === pathname);
}

export function resolvePage(pathname: string): PageMeta {
  const matched = resolveBaseItem(pathname);
  const index = matched
    ? `${String(navigationItems.findIndex((item) => item.to === matched.to) + 1).padStart(2, "0")}/${String(
        navigationItems.length,
      ).padStart(2, "0")}`
    : `00/${String(navigationItems.length).padStart(2, "0")}`;

  if (pathname.startsWith("/agents/")) {
    const agent = pathname.split("/").pop() || "unknown";
    return {
      eyebrow: "agent focus",
      title: `Agent ${agent}`,
      description: "Configuration, capacites et introspection detaillee de l'agent selectionne.",
      section: matched?.section || "Core",
      index,
    };
  }

  if (pathname.startsWith("/kill-life/")) {
    const workflowId = pathname.split("/").pop() || "workflow";
    return {
      eyebrow: "workflow editor",
      title: `Kill_LIFE ${workflowId}`,
      description: "Edition directe du graphe, validation, run local et dispatch GitHub pour les workflows Kill_LIFE.",
      section: matched?.section || "Integrations",
      index,
    };
  }

  if (matched) {
    return {
      eyebrow: matched.eyebrow,
      title: matched.title,
      description: matched.description,
      section: matched.section,
      index,
    };
  }

  return {
    eyebrow: "mascarade",
    title: "Mascarade",
    description: "Cockpit operateur pour la stack locale, les agents et les integrations runtime.",
    section: "Stack",
    index,
  };
}

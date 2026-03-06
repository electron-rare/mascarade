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
        icon: "⌘",
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
        icon: "▶",
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
        icon: "◎",
        label: "Agents",
        shortLabel: "Agents",
        hint: "registry + detail",
        eyebrow: "agent registry",
        title: "Agents",
        description: "Inventaire des agents exposes par le core et acces rapide a leurs details.",
        section: "Core",
      },
      {
        to: "/orchestrate",
        icon: "⚙",
        label: "Orchestrate",
        shortLabel: "Flow",
        hint: "multi-step control",
        eyebrow: "flow control",
        title: "Orchestrate",
        description: "Composer des runs multi-etapes et piloter l'orchestration depuis l'interface.",
        section: "Core",
      },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        to: "/logs",
        icon: "▒",
        label: "Logs",
        shortLabel: "Logs",
        hint: "live traces",
        eyebrow: "live observability",
        title: "Logs",
        description: "Flux temps reel des traces inter-agent et des incidents de service consolides par la gateway.",
        section: "Operations",
      },
      {
        to: "/metrics",
        icon: "▣",
        label: "Metrics",
        shortLabel: "Pulse",
        hint: "health + latency",
        eyebrow: "ops monitor",
        title: "Metrics",
        description: "Latence, sante et disponibilite des briques critiques de la stack Mascarade.",
        section: "Operations",
      },
      {
        to: "/infra",
        icon: "⬡",
        label: "Infrastructure",
        shortLabel: "Infra",
        hint: "raw stack map",
        eyebrow: "stack map",
        title: "Infrastructure",
        description: "Endpoints exposes, providers declares et etat brut de l'infrastructure.",
        section: "Operations",
      },
    ],
  },
  {
    label: "Integrations",
    items: [
      {
        to: "/notion",
        icon: "▤",
        label: "Notion",
        shortLabel: "Notion",
        hint: "knowledge bus",
        eyebrow: "knowledge bus",
        title: "Notion Browser",
        description: "Navigation des ressources Notion branchees sur la gateway Mascarade.",
        section: "Integrations",
      },
      {
        to: "/comfyui",
        icon: "◲",
        label: "ComfyUI",
        shortLabel: "Images",
        hint: "image workflows",
        eyebrow: "image lane",
        title: "ComfyUI",
        description: "Pilotage des workflows ComfyUI et verification rapide du pipeline image.",
        section: "Integrations",
      },
    ],
  },
];

export const navigationItems = navigationGroups.flatMap((group) => group.items);
export const mobileDockItems = navigationItems.filter((item) =>
  ["/", "/playground", "/agents", "/logs"].includes(item.to),
);

function resolveBaseItem(pathname: string): NavItem | undefined {
  if (pathname.startsWith("/agents/")) {
    return navigationItems.find((item) => item.to === "/agents");
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

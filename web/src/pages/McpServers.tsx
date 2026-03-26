import { useState, useCallback } from "react";
import { Badge, Card, InlineNotice, LoadingPanel } from "../components/ui";
import { useFetch } from "../hooks/useFetch";
import { post } from "../api/client";

type McpTool = {
  name: string;
  description?: string;
};

type McpServer = {
  name: string;
  description?: string;
  tools_count?: number;
  tools?: McpTool[];
  status?: "connected" | "disconnected" | "unknown";
  url?: string;
  doc_url?: string;
};

type McpSummary = {
  servers?: McpServer[];
};

const FALLBACK_SERVERS: McpServer[] = [
  {
    name: "Seeed KiCad MCP",
    description: "Seeed Studio component library and footprint resolution for KiCad.",
    tools_count: 12,
    status: "unknown",
    url: "https://mcp-kicad-seeed.saillant.cc",
    doc_url: "https://github.com/Seeed-Studio/kicad-mcp",
  },
  {
    name: "circuit-synth",
    description: "Circuit synthesis and netlist generation from natural language descriptions.",
    tools_count: 8,
    status: "unknown",
    url: "https://mcp-circuit-synth.saillant.cc",
  },
  {
    name: "kicad-happy",
    description: "KiCad project management, schematic editing and DRC automation.",
    tools_count: 15,
    status: "unknown",
    url: "https://mcp-kicad-happy.saillant.cc",
  },
  {
    name: "mixelpixx",
    description: "PCB layout assistance, component placement and routing suggestions.",
    tools_count: 10,
    status: "unknown",
    url: "https://mcp-mixelpixx.saillant.cc",
  },
  {
    name: "SPICEBridge",
    description: "SPICE simulation bridge: run ngspice/LTspice from MCP tool calls.",
    tools_count: 6,
    status: "unknown",
    url: "https://mcp-spicebridge.saillant.cc",
  },
];

function statusBadge(status?: string) {
  if (status === "connected") return <Badge color="accent">connected</Badge>;
  if (status === "disconnected") return <Badge color="error">disconnected</Badge>;
  return <Badge color="muted">unknown</Badge>;
}

function ServerCard({
  server,
  onPing,
  pinging,
}: {
  server: McpServer;
  onPing: (name: string) => void;
  pinging: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const tools = server.tools ?? [];

  return (
    <div className="rounded-3xl border border-border/80 bg-black/20 p-5 transition-all duration-200 hover:border-accent/22">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-[14px] font-semibold uppercase tracking-[0.14em] text-accent">
            {server.name}
          </h3>
          {server.description && (
            <p className="mt-1 text-xs leading-5 text-amber-100/55">{server.description}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {statusBadge(server.status)}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge color="muted">{server.tools_count ?? tools.length} tools</Badge>
        {server.url && (
          <span className="text-[10px] font-mono text-amber-50/35 tracking-wider truncate max-w-[260px]">
            {server.url.replace(/^https?:\/\//, "")}
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          onClick={() => onPing(server.name)}
          disabled={pinging}
          className="inline-flex min-h-8 items-center rounded-full border border-accent/35 bg-accent/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
        >
          {pinging ? "pinging..." : "ping"}
        </button>
        {tools.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="inline-flex min-h-8 items-center rounded-full border border-border/80 bg-black/25 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted transition-colors hover:text-accent"
          >
            {expanded ? "hide tools" : "show tools"}
          </button>
        )}
        {server.doc_url && (
          <a
            href={server.doc_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-8 items-center rounded-full border border-border/80 bg-black/25 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted transition-colors hover:text-accent"
          >
            docs
          </a>
        )}
      </div>

      {expanded && tools.length > 0 && (
        <div className="mt-4 space-y-1 rounded-2xl border border-border/60 bg-black/30 p-3">
          {tools.map((tool) => (
            <div key={tool.name} className="flex items-baseline gap-2 py-1">
              <span className="text-[11px] font-mono font-semibold text-accent/80">{tool.name}</span>
              {tool.description && (
                <span className="text-[10px] text-amber-50/40 truncate">{tool.description}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function McpServers() {
  const { data, loading, error } = useFetch<McpSummary>("/api/ops/mcp/summary", {
    pollIntervalMs: 30_000,
  });

  const [pingStates, setPingStates] = useState<Record<string, "pinging" | "ok" | "fail">>({});

  const handlePing = useCallback(async (name: string) => {
    setPingStates((prev) => ({ ...prev, [name]: "pinging" }));
    try {
      await post("/api/ops/mcp/ping", { server: name });
      setPingStates((prev) => ({ ...prev, [name]: "ok" }));
    } catch {
      setPingStates((prev) => ({ ...prev, [name]: "fail" }));
    }
    setTimeout(() => {
      setPingStates((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }, 3000);
  }, []);

  const servers: McpServer[] = data?.servers && data.servers.length > 0
    ? data.servers
    : FALLBACK_SERVERS;

  const connected = servers.filter((s) => s.status === "connected").length;
  const totalTools = servers.reduce((sum, s) => sum + (s.tools_count ?? s.tools?.length ?? 0), 0);

  if (loading && !data) {
    return (
      <LoadingPanel
        title="Loading MCP servers"
        message="Fetching MCP server registry and tool inventory."
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card title="MCP Servers">
        <p className="text-sm leading-7 text-amber-100/60">
          Serveurs Model Context Protocol integres a Mascarade. 5 serveurs KiCad pour la conception electronique.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge color="accent">{servers.length} servers</Badge>
          <Badge color={connected > 0 ? "accent" : "muted"}>{connected} connected</Badge>
          <Badge color="muted">{totalTools} tools</Badge>
        </div>
      </Card>

      {error && !data && (
        <InlineNotice
          title="mcp registry unavailable"
          message={error}
          tone="error"
          className="mx-auto max-w-3xl"
        />
      )}
      {error && data && (
        <InlineNotice
          title="refresh note"
          message={`Refresh warning: ${error}`}
          tone="info"
        />
      )}

      <Card title="Server Registry">
        <div className="mt-2 space-y-4">
          {servers.map((server) => (
            <ServerCard
              key={server.name}
              server={server}
              onPing={handlePing}
              pinging={pingStates[server.name] === "pinging"}
            />
          ))}
        </div>
      </Card>
    </div>
  );
}

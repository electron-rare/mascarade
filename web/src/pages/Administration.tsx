import { useCallback, useState } from "react";
import { useFetch } from "../hooks/useFetch";
import { post, del } from "../api/client";
import { Badge, Button, Card, InlineNotice } from "../components/ui";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type ServiceDef = {
  name: string;
  machine: string;
  port: number;
};

type ServiceStatus = {
  name: string;
  status?: "running" | "stopped" | "error" | "unknown";
  uptime?: string;
  port?: number;
  machine?: string;
};

type FleetSyncNode = {
  name: string;
  status?: "synced" | "syncing" | "error" | "idle";
  last_sync?: string;
};

type TrainingStatus = {
  running?: boolean;
  dataset?: string;
  base_model?: string;
  gpu_utilization?: number;
  gpu_status?: "idle" | "active" | "error";
};

type PipelineStep = {
  id: string;
  label: string;
  status: "idle" | "running" | "done" | "failed";
};

type AdminUser = {
  id?: string;
  username: string;
  role: "admin" | "operator" | "viewer";
  created_at?: string;
};

type AuditEntry = {
  timestamp: string;
  action: string;
  user?: string;
  detail?: string;
};

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const SERVICE_MANIFEST: ServiceDef[] = [
  { name: "mascarade-core", machine: "photon", port: 8000 },
  { name: "mascarade-api", machine: "Tower", port: 8080 },
  { name: "argilla", machine: "Tower", port: 6900 },
  { name: "langfuse", machine: "Tower", port: 3000 },
  { name: "ollama", machine: "KXKM-AI", port: 11434 },
];

const FLEET_MACHINES = ["photon", "KXKM-AI", "Tower", "grosmac", "Cils"];

const DATASETS = [
  "kicad-instruct-v3",
  "spice-instruct-v2",
  "embedded-mixed-v1",
  "electronics-qa-v4",
  "mascarade-dialog-v2",
];

const BASE_MODELS = [
  "mistral-7b-instruct-v0.3",
  "codestral-22b-v0.1",
  "mistral-small-24b",
  "llama-3.1-8b-instruct",
  "qwen2.5-coder-7b",
];

const EXTERNAL_LINKS = [
  { label: "Grafana", url: "http://192.168.0.119:3100" },
  { label: "Langfuse", url: "http://192.168.0.120:3000" },
  { label: "Argilla", url: "http://192.168.0.120:6900" },
  { label: "Nextcloud", url: "http://192.168.0.120:8082" },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function statusBadgeColor(status?: string): "accent" | "error" | "warning" | "muted" {
  if (status === "running" || status === "synced" || status === "done" || status === "active") return "accent";
  if (status === "error" || status === "failed" || status === "stopped") return "error";
  if (status === "syncing" || status === "running") return "warning";
  return "muted";
}

function pipelineChipClass(status: string): string {
  if (status === "done") return "border-green-400/60 bg-green-500/20 text-emerald-100";
  if (status === "running") return "border-warning/60 bg-warning/20 text-warning animate-pulse";
  if (status === "failed") return "border-red-400/60 bg-red-500/20 text-red-200";
  return "border-border/80 bg-black/30 text-muted";
}

function formatTs(ts?: string): string {
  if (!ts) return "--";
  try {
    return new Date(ts).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function Administration() {
  /* ---------- Service control ---------- */
  const services = useFetch<{ services: ServiceStatus[] }>("/api/admin/services", {
    pollIntervalMs: 10_000,
  });
  const serviceList: ServiceStatus[] = services.data?.services ?? SERVICE_MANIFEST.map((s) => ({
    name: s.name,
    status: undefined,
    port: s.port,
    machine: s.machine,
  }));
  const [serviceAction, setServiceAction] = useState<Record<string, string>>({});

  const handleServiceAction = useCallback(async (name: string, action: "start" | "stop" | "restart") => {
    setServiceAction((prev) => ({ ...prev, [name]: action }));
    try {
      await post(`/api/admin/services/${name}/${action}`);
    } catch {
      /* best-effort */
    } finally {
      setServiceAction((prev) => ({ ...prev, [name]: "" }));
      void services.refetch();
    }
  }, [services]);

  /* ---------- Fleet sync ---------- */
  const fleet = useFetch<{ nodes: FleetSyncNode[] }>("/api/admin/fleet/sync", {
    pollIntervalMs: 30_000,
  });
  const fleetNodes: FleetSyncNode[] = fleet.data?.nodes ?? FLEET_MACHINES.map((n) => ({ name: n }));
  const [syncing, setSyncing] = useState(false);

  const syncAll = useCallback(async () => {
    setSyncing(true);
    try {
      await post("/api/admin/fleet/sync-all");
    } catch {
      /* best-effort */
    } finally {
      setSyncing(false);
      void fleet.refetch();
    }
  }, [fleet]);

  /* ---------- Training control ---------- */
  const training = useFetch<TrainingStatus>("/api/admin/training/status", {
    pollIntervalMs: 10_000,
  });
  const [selectedDataset, setSelectedDataset] = useState(DATASETS[0]);
  const [selectedModel, setSelectedModel] = useState(BASE_MODELS[0]);
  const [trainingAction, setTrainingAction] = useState("");

  const handleTraining = useCallback(async (action: "start" | "stop") => {
    setTrainingAction(action);
    try {
      await post(`/api/admin/training/${action}`, { dataset: selectedDataset, base_model: selectedModel });
    } catch {
      /* best-effort */
    } finally {
      setTrainingAction("");
      void training.refetch();
    }
  }, [training, selectedDataset, selectedModel]);

  /* ---------- Deploy pipeline ---------- */
  const [pipeline, setPipeline] = useState<PipelineStep[]>([
    { id: "benchmark", label: "Run Benchmark", status: "idle" },
    { id: "deploy", label: "Deploy to Photon", status: "idle" },
    { id: "publish", label: "Publish to HuggingFace", status: "idle" },
  ]);

  const triggerPipeline = useCallback(async (stepId: string) => {
    setPipeline((prev) => prev.map((s) => (s.id === stepId ? { ...s, status: "running" as const } : s)));
    try {
      const res = await post<{ status: string }>(`/api/admin/pipeline/${stepId}`);
      const finalStatus = res?.status === "ok" ? "done" : "done";
      setPipeline((prev) => prev.map((s) => (s.id === stepId ? { ...s, status: finalStatus as "done" } : s)));
    } catch {
      setPipeline((prev) => prev.map((s) => (s.id === stepId ? { ...s, status: "failed" as const } : s)));
    }
  }, []);

  /* ---------- Users ---------- */
  const users = useFetch<{ users: AdminUser[] }>("/api/users", { pollIntervalMs: 30_000 });
  const userList: AdminUser[] = users.data?.users ?? [];
  const [newUsername, setNewUsername] = useState("");
  const [newRole, setNewRole] = useState<"admin" | "operator" | "viewer">("operator");
  const [userBusy, setUserBusy] = useState(false);

  const createUser = useCallback(async () => {
    if (!newUsername.trim()) return;
    setUserBusy(true);
    try {
      await post("/api/users", { username: newUsername.trim(), role: newRole });
      setNewUsername("");
    } catch {
      /* best-effort */
    } finally {
      setUserBusy(false);
      void users.refetch();
    }
  }, [newUsername, newRole, users]);

  const deleteUser = useCallback(async (username: string) => {
    try {
      await del(`/api/users/${username}`);
    } catch {
      /* best-effort */
    } finally {
      void users.refetch();
    }
  }, [users]);

  /* ---------- Audit ---------- */
  const audit = useFetch<{ entries: AuditEntry[] }>("/api/admin/audit", { pollIntervalMs: 15_000 });
  const auditEntries: AuditEntry[] = audit.data?.entries ?? [];

  const health = useFetch<{ checks: Record<string, boolean> }>("/api/health", { pollIntervalMs: 15_000 });

  /* ------------------------------------------------------------------ */
  /*  Render                                                             */
  /* ------------------------------------------------------------------ */

  return (
    <div className="space-y-6">

      {/* ---------- Header ---------- */}
      <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="screen-label">administration</p>
            <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
              Control panel
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
              Services, fleet sync, training, deploy pipeline, users et audit log centralises.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                services {serviceList.length}
              </span>
              <span className="status-chip border-green-400/60 bg-green-500/20 text-emerald-100">
                online {serviceList.filter((s) => s.status === "running").length}
              </span>
              <span className="status-chip border-border/80 bg-black/30 text-muted">
                users {userList.length}
              </span>
            </div>
          </div>

          <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">services</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                {String(serviceList.length).padStart(2, "0")}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Services declares dans le manifest admin.
              </p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">fleet nodes</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                {String(FLEET_MACHINES.length).padStart(2, "0")}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Machines dans le cluster fleet.
              </p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">gpu</p>
              <p className={[
                "mt-3 text-2xl font-semibold uppercase tracking-[0.12em]",
                training.data?.gpu_status === "active" ? "text-[#8cffb7]" : "text-accent",
              ].join(" ")}>
                {training.data?.gpu_status ?? "idle"}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Status GPU du worker de training.
              </p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">audit</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                {String(auditEntries.length).padStart(2, "0")}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Actions admin recentes enregistrees.
              </p>
            </div>
          </div>
        </div>
      </Card>

      {services.error ? (
        <InlineNotice
          title="services api"
          message={`Services endpoint: ${services.error}. Affichage manifest statique.`}
          tone="info"
        />
      ) : null}

      {/* ================================================================ */}
      {/*  Section 1: Service Control                                      */}
      {/* ================================================================ */}
      <Card title="Service control">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {serviceList.map((svc) => {
            const manifest = SERVICE_MANIFEST.find((m) => m.name === svc.name);
            const busy = !!serviceAction[svc.name];
            return (
              <div
                key={svc.name}
                className="rounded-[1.5rem] border border-border/80 bg-black/20 p-4"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                      {svc.name}
                    </p>
                    <p className="mt-1 text-[11px] text-amber-100/50">
                      {svc.machine ?? manifest?.machine} : {svc.port ?? manifest?.port}
                    </p>
                  </div>
                  <Badge color={statusBadgeColor(svc.status)}>
                    {svc.status ?? "unknown"}
                  </Badge>
                </div>
                {svc.uptime ? (
                  <p className="mt-2 text-[10px] uppercase tracking-[0.16em] text-muted">
                    uptime {svc.uptime}
                  </p>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    disabled={busy}
                    className="rounded-lg border border-green-400/40 bg-green-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-200 transition hover:bg-green-500/20 disabled:opacity-40"
                    onClick={() => void handleServiceAction(svc.name, "start")}
                  >
                    {serviceAction[svc.name] === "start" ? "..." : "start"}
                  </button>
                  <button
                    disabled={busy}
                    className="rounded-lg border border-red-400/40 bg-red-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-red-200 transition hover:bg-red-500/20 disabled:opacity-40"
                    onClick={() => void handleServiceAction(svc.name, "stop")}
                  >
                    {serviceAction[svc.name] === "stop" ? "..." : "stop"}
                  </button>
                  <button
                    disabled={busy}
                    className="rounded-lg border border-accent/35 bg-accent/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-accent transition hover:bg-accent/20 disabled:opacity-40"
                    onClick={() => void handleServiceAction(svc.name, "restart")}
                  >
                    {serviceAction[svc.name] === "restart" ? "..." : "restart"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* ================================================================ */}
      {/*  Section 2: Fleet Sync                                           */}
      {/* ================================================================ */}
      <Card title="Fleet sync">
        <div className="mb-4 flex items-center gap-4">
          <Button
            variant="ghost"
            className="rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-accent"
            onClick={() => void syncAll()}
            disabled={syncing}
          >
            {syncing ? "syncing..." : "sync all"}
          </Button>
          <p className="text-[11px] text-amber-100/50">
            git pull sur toutes les machines du cluster
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {fleetNodes.map((node) => (
            <div
              key={node.name}
              className="flex items-center justify-between rounded-2xl border border-border/80 bg-black/20 px-4 py-3"
            >
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                  {node.name}
                </p>
                <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-muted">
                  last sync {formatTs(node.last_sync)}
                </p>
              </div>
              <Badge color={statusBadgeColor(node.status)}>
                {node.status ?? "idle"}
              </Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* ================================================================ */}
      {/*  Section 3: Training Control                                     */}
      {/* ================================================================ */}
      <Card title="Training control">
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Controls */}
          <div className="space-y-4">
            <div>
              <label className="text-[10px] uppercase tracking-[0.2em] text-muted">dataset</label>
              <select
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
                className="mt-1 block w-full rounded-xl border border-border/80 bg-black/30 px-3 py-2 text-sm text-amber-100/80 outline-none focus:border-accent/60"
              >
                {DATASETS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-[0.2em] text-muted">base model</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="mt-1 block w-full rounded-xl border border-border/80 bg-black/30 px-3 py-2 text-sm text-amber-100/80 outline-none focus:border-accent/60"
              >
                {BASE_MODELS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
            <div className="flex gap-3">
              <Button
                variant="ghost"
                className="rounded-2xl border border-green-400/40 bg-green-500/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-emerald-200"
                onClick={() => void handleTraining("start")}
                disabled={!!trainingAction || training.data?.running === true}
              >
                {trainingAction === "start" ? "starting..." : "start training"}
              </Button>
              <Button
                variant="ghost"
                className="rounded-2xl border border-red-400/40 bg-red-500/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-red-200"
                onClick={() => void handleTraining("stop")}
                disabled={!!trainingAction || training.data?.running === false}
              >
                {trainingAction === "stop" ? "stopping..." : "stop training"}
              </Button>
            </div>
          </div>

          {/* GPU status */}
          <div className="rounded-2xl border border-accent/20 bg-accent/5 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-accent">gpu status</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div>
                <p className="text-[10px] uppercase tracking-[0.16em] text-muted">status</p>
                <p className={[
                  "mt-1 text-sm font-semibold uppercase tracking-[0.12em]",
                  training.data?.gpu_status === "active" ? "text-[#8cffb7]" : training.data?.gpu_status === "error" ? "text-error" : "text-accent",
                ].join(" ")}>
                  {training.data?.gpu_status ?? "idle"}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-[0.16em] text-muted">utilization</p>
                <p className="mt-1 text-sm text-amber-100/78">
                  {training.data?.gpu_utilization !== undefined ? `${Math.round(training.data.gpu_utilization)}%` : "--"}
                </p>
                {training.data?.gpu_utilization !== undefined ? (
                  <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-border/30">
                    <div
                      className={`h-full rounded-full ${training.data.gpu_utilization >= 90 ? "bg-error" : training.data.gpu_utilization >= 70 ? "bg-warning" : "bg-[#8cffb7]"}`}
                      style={{ width: `${Math.min(training.data.gpu_utilization, 100)}%` }}
                    />
                  </div>
                ) : null}
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-[0.16em] text-muted">running</p>
                <p className="mt-1 text-sm text-amber-100/78">
                  {training.data?.running ? "yes" : "no"}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-[0.16em] text-muted">dataset</p>
                <p className="mt-1 text-sm text-amber-100/78">
                  {training.data?.dataset ?? "--"}
                </p>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* ================================================================ */}
      {/*  Section 4: Deploy Pipeline                                      */}
      {/* ================================================================ */}
      <Card title="Deploy pipeline">
        <div className="grid gap-3 sm:grid-cols-3">
          {pipeline.map((step) => (
            <div
              key={step.id}
              className="rounded-[1.5rem] border border-border/80 bg-black/20 p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                  {step.label}
                </p>
                <span className={`status-chip ${pipelineChipClass(step.status)}`}>
                  {step.status}
                </span>
              </div>
              <div className="mt-4">
                <button
                  disabled={step.status === "running"}
                  className="rounded-lg border border-accent/35 bg-accent/10 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-accent transition hover:bg-accent/20 disabled:opacity-40"
                  onClick={() => void triggerPipeline(step.id)}
                >
                  {step.status === "running" ? "running..." : "run"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* ================================================================ */}
      {/*  Section 5: Users                                                */}
      {/* ================================================================ */}
      <Card title="Users">
        {/* Create user form */}
        <div className="mb-4 flex flex-wrap items-end gap-3 rounded-2xl border border-border/80 bg-black/20 p-4">
          <div className="flex-1 min-w-[160px]">
            <label className="text-[10px] uppercase tracking-[0.2em] text-muted">username</label>
            <input
              type="text"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              placeholder="new user"
              className="mt-1 block w-full rounded-xl border border-border/80 bg-black/30 px-3 py-2 text-sm text-amber-100/80 placeholder:text-muted outline-none focus:border-accent/60"
            />
          </div>
          <div className="min-w-[120px]">
            <label className="text-[10px] uppercase tracking-[0.2em] text-muted">role</label>
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value as "admin" | "operator" | "viewer")}
              className="mt-1 block w-full rounded-xl border border-border/80 bg-black/30 px-3 py-2 text-sm text-amber-100/80 outline-none focus:border-accent/60"
            >
              <option value="admin">admin</option>
              <option value="operator">operator</option>
              <option value="viewer">viewer</option>
            </select>
          </div>
          <Button
            variant="ghost"
            className="rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-accent"
            onClick={() => void createUser()}
            disabled={userBusy || !newUsername.trim()}
          >
            {userBusy ? "creating..." : "create user"}
          </Button>
        </div>

        {/* User list */}
        {userList.length === 0 ? (
          <p className="text-sm text-amber-100/40">No users loaded from API.</p>
        ) : (
          <div className="space-y-2">
            {userList.map((user) => (
              <div
                key={user.username}
                className="flex items-center justify-between rounded-2xl border border-border/80 bg-black/20 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <p className="text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                    {user.username}
                  </p>
                  <Badge color={user.role === "admin" ? "accent" : user.role === "operator" ? "warning" : "muted"}>
                    {user.role}
                  </Badge>
                  {user.created_at ? (
                    <span className="text-[10px] text-muted">{formatTs(user.created_at)}</span>
                  ) : null}
                </div>
                <button
                  className="rounded-lg border border-red-400/40 bg-red-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-red-200 transition hover:bg-red-500/20"
                  onClick={() => void deleteUser(user.username)}
                >
                  delete
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* ================================================================ */}
      {/*  Section 6: Logs & Audit                                         */}
      {/* ================================================================ */}
      <Card title="Logs & audit">
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Recent actions */}
          <div>
            <p className="screen-label">recent admin actions</p>
            <div className="mt-3 max-h-[320px] space-y-1 overflow-y-auto">
              {auditEntries.length === 0 ? (
                <p className="text-sm text-amber-100/40">No audit entries loaded.</p>
              ) : (
                auditEntries.slice(0, 20).map((entry, i) => (
                  <div
                    key={`${entry.timestamp}-${i}`}
                    className="flex items-start gap-3 rounded-xl border border-border/60 bg-black/10 px-3 py-2"
                  >
                    <span className="shrink-0 font-mono text-[10px] text-muted">
                      {formatTs(entry.timestamp)}
                    </span>
                    <span className="text-[11px] text-amber-100/70">
                      {entry.user ? <span className="font-semibold text-accent">{entry.user}</span> : null}
                      {entry.user ? " " : ""}
                      {entry.action}
                      {entry.detail ? ` -- ${entry.detail}` : ""}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* System health + external links */}
          <div className="space-y-4">
            <div>
              <p className="screen-label">system health</p>
              <div className="mt-3 space-y-1">
                {health.data?.checks ? (
                  Object.entries(health.data.checks).map(([name, ok]) => (
                    <div
                      key={name}
                      className="flex items-center justify-between rounded-xl border border-border/60 bg-black/10 px-3 py-2"
                    >
                      <span className="text-[11px] uppercase tracking-[0.12em] text-amber-100/70">{name}</span>
                      <Badge color={ok ? "accent" : "error"}>{ok ? "ok" : "fail"}</Badge>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-amber-100/40">Health data not loaded.</p>
                )}
              </div>
            </div>

            <div>
              <p className="screen-label">external links</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {EXTERNAL_LINKS.map((link) => (
                  <a
                    key={link.label}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-lg border border-accent/35 bg-accent/10 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-accent transition hover:bg-accent/20"
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

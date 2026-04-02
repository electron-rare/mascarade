import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useFetch } from "../hooks/useFetch";
import { del, get, isPersisted, post, put } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Badge, Button, Card, InlineNotice, JsonView, LoadingPanel } from "../components/ui";

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
  { name: "mascarade-api", machine: "Tower", port: 3100 },
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
  { label: "Drive (frontend)", url: "http://192.168.0.120:8086" },
  { label: "Nextcloud (backend)", url: "http://192.168.0.120:8088" },
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

function ControlContent() {
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

/* ================================================================== */
/*  Fleet tab content (merged from Fleet.tsx + P2P.tsx)                 */
/* ================================================================== */

type FleetNodeInfo = {
  node_id?: string;
  name?: string;
  ip?: string;
  role?: string;
  status?: "online" | "offline" | "degraded";
  services?: string[];
  cpu_percent?: number;
  ram_percent?: number;
  disk_percent?: number;
  gpu?: {
    model?: string;
    vram_total_gb?: number;
    vram_used_gb?: number;
    utilization_percent?: number;
  };
  last_sync?: string;
  git_commit?: string;
};

type FleetClusterPayload = {
  nodes?: FleetNodeInfo[];
};

type FleetP2PPeer = {
  node_id?: string;
  name?: string;
  ip?: string;
  status?: string;
};

type FleetP2PPayload = {
  peers?: FleetP2PPeer[];
};

const FLEET_MANIFEST_DATA: {
  name: string;
  ip: string;
  role: string;
  services: string[];
  hasGpu: boolean;
}[] = [
  { name: "photon", ip: "192.168.0.119", role: "Prod, edge proxy + public entrypoint", services: ["edge-proxy", "gateway", "qdrant", "searxng", "comfyui"], hasGpu: false },
  { name: "KXKM-AI", ip: "100.87.54.119", role: "GPU RTX 4090, finetune", services: ["ollama", "finetune", "comfyui", "argilla"], hasGpu: true },
  { name: "Tower", ip: "192.168.0.120", role: "API, Drive frontend, Nextcloud backend", services: ["mascarade-api", "drive", "nextcloud", "ollama"], hasGpu: true },
  { name: "grosmac", ip: "100.80.178.42", role: "Dev", services: ["core", "ollama", "dev-gateway"], hasGpu: false },
  { name: "Cils", ip: "100.126.225.111", role: "macOS Intel", services: ["ollama"], hasGpu: false },
];

function fleetStatusTone(status: string | undefined): string {
  if (status === "online") return "text-[#8cffb7]";
  if (status === "degraded") return "text-warning";
  return "text-error";
}

function fleetStatusChipTone(status: string | undefined): string {
  if (status === "online") return "border-green-400/60 bg-green-500/20 text-emerald-100";
  if (status === "degraded") return "border-warning/60 bg-warning/20 text-warning";
  return "border-red-400/60 bg-red-500/20 text-red-200";
}

function fleetUsageBar(percent: number | undefined): string {
  if (percent === undefined || percent === null) return "bg-border/40";
  if (percent >= 90) return "bg-error";
  if (percent >= 70) return "bg-warning";
  return "bg-[#8cffb7]";
}

function fleetFormatPercent(value: number | undefined): string {
  if (value === undefined || value === null) return "--";
  return `${Math.round(value)}%`;
}

function fleetShortCommit(hash: string | undefined): string {
  if (!hash) return "--";
  return hash.substring(0, 7);
}

function fleetFormatSync(ts: string | undefined): string {
  if (!ts) return "--";
  try {
    const date = new Date(ts);
    return date.toLocaleString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit", day: "2-digit", month: "2-digit" });
  } catch {
    return ts;
  }
}

function FleetContent() {
  const cluster = useFetch<FleetClusterPayload>("/api/cluster/nodes", { pollIntervalMs: 15_000 });
  const p2p = useFetch<FleetP2PPayload>("/api/p2p", { pollIntervalMs: 15_000 });

  const apiNodes = cluster.data?.nodes ?? [];
  const p2pPeers = p2p.data?.peers ?? [];

  const machines = useMemo(() => {
    return FLEET_MANIFEST_DATA.map((manifest) => {
      const apiNode = apiNodes.find(
        (n) =>
          n.name?.toLowerCase() === manifest.name.toLowerCase() ||
          n.node_id?.toLowerCase() === manifest.name.toLowerCase() ||
          n.ip === manifest.ip,
      );
      const p2pPeer = p2pPeers.find(
        (p) =>
          p.name?.toLowerCase() === manifest.name.toLowerCase() ||
          p.node_id?.toLowerCase() === manifest.name.toLowerCase() ||
          p.ip === manifest.ip,
      );
      return {
        ...manifest,
        status: apiNode?.status ?? (p2pPeer?.status as "online" | "offline" | "degraded" | undefined) ?? undefined,
        cpu_percent: apiNode?.cpu_percent,
        ram_percent: apiNode?.ram_percent,
        disk_percent: apiNode?.disk_percent,
        gpu: apiNode?.gpu,
        last_sync: apiNode?.last_sync,
        git_commit: apiNode?.git_commit,
        liveServices: apiNode?.services ?? manifest.services,
      };
    });
  }, [apiNodes, p2pPeers]);

  const onlineCount = machines.filter((m) => m.status === "online").length;
  const degradedCount = machines.filter((m) => m.status === "degraded").length;

  if (cluster.loading && !cluster.data && !p2p.data) {
    return (
      <LoadingPanel
        title="Loading fleet inventory"
        message="Collecting cluster node status, resource usage and peer discovery."
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="screen-label">fleet control</p>
            <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
              Cluster machines, services and resource allocation
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
              Vue consolidee des 5 machines du cluster: status, services actifs, utilisation CPU/RAM/disque, GPU et derniere synchronisation git.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="status-chip border-accent/35 bg-accent/10 text-accent">machines {machines.length}</span>
              <span className="status-chip border-green-400/60 bg-green-500/20 text-emerald-100">online {onlineCount}</span>
              {degradedCount > 0 ? (
                <span className="status-chip border-warning/60 bg-warning/20 text-warning">degraded {degradedCount}</span>
              ) : null}
              <span className="status-chip border-border/80 bg-black/30 text-muted">p2p peers {p2pPeers.length}</span>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button
                variant="ghost"
                className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                onClick={() => { void cluster.refetch(); void p2p.refetch(); }}
              >
                refresh all
              </Button>
            </div>
          </div>
          <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">fleet size</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">{machines.length.toString().padStart(2, "0")}</p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">online</p>
              <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", onlineCount > 0 ? "text-[#8cffb7]" : "text-error"].join(" ")}>{onlineCount.toString().padStart(2, "0")}</p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">gpu nodes</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">{machines.filter((m) => m.hasGpu).length.toString().padStart(2, "0")}</p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">total services</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">{machines.reduce((acc, m) => acc + m.liveServices.length, 0).toString().padStart(2, "0")}</p>
            </div>
          </div>
        </div>
      </Card>

      {cluster.error ? (
        <InlineNotice title="cluster api note" message={`Cluster endpoint: ${cluster.error}. Affichage base sur le manifest statique.`} tone="info" />
      ) : null}

      <Card title="Machine inventory">
        <div className="space-y-4">
          {machines.map((machine) => (
            <div key={machine.name} className="rounded-[1.5rem] border border-border/80 bg-black/20 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="screen-label">{machine.name}</p>
                  <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">{machine.ip}</p>
                  <p className="mt-1 text-xs leading-5 text-amber-100/60">{machine.role}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className={`status-chip ${fleetStatusChipTone(machine.status)}`}>{machine.status ?? "unknown"}</span>
                  {machine.hasGpu ? <Badge color="accent">gpu</Badge> : null}
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {machine.liveServices.map((service) => (
                  <Badge key={`${machine.name}-${service}`} color="muted">{service}</Badge>
                ))}
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">cpu</p>
                  <p className={["mt-2 text-sm", machine.cpu_percent !== undefined ? fleetStatusTone(machine.cpu_percent < 90 ? "online" : "degraded") : "text-amber-100/78"].join(" ")}>
                    {fleetFormatPercent(machine.cpu_percent)}
                  </p>
                  {machine.cpu_percent !== undefined ? (
                    <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-border/30">
                      <div className={`h-full rounded-full ${fleetUsageBar(machine.cpu_percent)}`} style={{ width: `${Math.min(machine.cpu_percent, 100)}%` }} />
                    </div>
                  ) : null}
                </div>
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">ram</p>
                  <p className={["mt-2 text-sm", machine.ram_percent !== undefined ? fleetStatusTone(machine.ram_percent < 90 ? "online" : "degraded") : "text-amber-100/78"].join(" ")}>
                    {fleetFormatPercent(machine.ram_percent)}
                  </p>
                  {machine.ram_percent !== undefined ? (
                    <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-border/30">
                      <div className={`h-full rounded-full ${fleetUsageBar(machine.ram_percent)}`} style={{ width: `${Math.min(machine.ram_percent, 100)}%` }} />
                    </div>
                  ) : null}
                </div>
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">disk</p>
                  <p className={["mt-2 text-sm", machine.disk_percent !== undefined ? fleetStatusTone(machine.disk_percent < 90 ? "online" : "degraded") : "text-amber-100/78"].join(" ")}>
                    {fleetFormatPercent(machine.disk_percent)}
                  </p>
                  {machine.disk_percent !== undefined ? (
                    <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-border/30">
                      <div className={`h-full rounded-full ${fleetUsageBar(machine.disk_percent)}`} style={{ width: `${Math.min(machine.disk_percent, 100)}%` }} />
                    </div>
                  ) : null}
                </div>
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">git</p>
                  <p className="mt-2 font-mono text-sm text-amber-100/78">{fleetShortCommit(machine.git_commit)}</p>
                </div>
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">last sync</p>
                  <p className="mt-2 text-sm text-amber-100/78">{fleetFormatSync(machine.last_sync)}</p>
                </div>
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">actions</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      className="rounded-lg border border-accent/35 bg-accent/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-accent transition hover:bg-accent/20"
                      onClick={() => void cluster.refetch()}
                    >
                      sync
                    </button>
                    <a
                      href={`ssh://${machine.ip !== "local" ? machine.ip : "localhost"}`}
                      className="rounded-lg border border-border/80 bg-black/30 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted transition hover:text-accent"
                    >
                      ssh
                    </a>
                  </div>
                </div>
              </div>
              {machine.hasGpu ? (
                <div className="mt-4 rounded-2xl border border-accent/20 bg-accent/5 p-4">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-accent">gpu info</p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-4">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">model</p>
                      <p className="mt-1 text-sm font-semibold uppercase tracking-[0.12em] text-accent">{machine.gpu?.model ?? "RTX 4090"}</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">vram total</p>
                      <p className="mt-1 text-sm text-amber-100/78">{machine.gpu?.vram_total_gb ? `${machine.gpu.vram_total_gb} GB` : "24 GB"}</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">vram used</p>
                      <p className="mt-1 text-sm text-amber-100/78">{machine.gpu?.vram_used_gb ? `${machine.gpu.vram_used_gb} GB` : "--"}</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">utilization</p>
                      <p className="mt-1 text-sm text-amber-100/78">{fleetFormatPercent(machine.gpu?.utilization_percent)}</p>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </Card>

      <Card title="Raw payloads">
        <div className="space-y-4">
          <div>
            <p className="screen-label">cluster nodes</p>
            <div className="mt-3"><JsonView data={cluster.data ?? {}} /></div>
          </div>
          <div>
            <p className="screen-label">p2p discovery</p>
            <div className="mt-3"><JsonView data={p2p.data ?? {}} /></div>
          </div>
        </div>
      </Card>
    </div>
  );
}

/* ================================================================== */
/*  Settings tab content (merged from Settings.tsx)                     */
/* ================================================================== */

interface SettingsFieldStatus {
  env: string;
  label: string;
  configured: boolean;
  hint: string;
  secret: boolean;
  classification?: string;
  criticality?: string;
  auth_modes?: string[];
}

interface SettingsProviderStatus {
  name: string;
  label: string;
  classification?: string;
  criticality?: string;
  required_when?: string;
  used_by?: string[];
  configured: boolean;
  active: boolean;
  fields: SettingsFieldStatus[];
  default_model: string | null;
  models: string[];
  enabled?: boolean;
  toggle_env?: string;
  auth_mode?: string;
  auth_mode_env?: string;
  auth_modes?: string[];
}

interface SettingsProviderMutationResponse {
  status: string;
  active: boolean;
  configured: boolean;
  message?: string;
  updated_env?: string[];
  cleared_env?: string[];
  restarted_services?: string[];
}

interface SettingsRuntimeSecretFieldStatus {
  env: string;
  label: string;
  configured: boolean;
  hint: string;
  secret: boolean;
  classification?: string;
  criticality?: string;
  restart_services: string[];
  auth_modes?: string[];
  providers?: string[];
  active?: boolean;
}

interface SettingsRuntimeSecretGroupStatus {
  name: string;
  label: string;
  description: string;
  classification?: string;
  criticality?: string;
  required_when?: string;
  used_by?: string[];
  configured: boolean;
  configured_count: number;
  field_count: number;
  generate_supported: boolean;
  restart_services: string[];
  fields: SettingsRuntimeSecretFieldStatus[];
  provider?: string;
  provider_env?: string;
  providers?: string[];
  auth_mode?: string;
  auth_mode_env?: string;
  auth_modes?: string[];
}

interface SettingsRuntimeSecretMutationResponse {
  status: string;
  message?: string;
  group: SettingsRuntimeSecretGroupStatus;
  updated_env?: string[];
  cleared_env?: string[];
  restarted_services?: string[];
  client_token?: string;
  generated_value?: string;
  extra_info?: string;
}

type SettingsSaveState = "idle" | "saving" | "ok" | "error";

function settingsCriticalityMeta(level?: string) {
  switch (level) {
    case "required-security":
      return { label: "required security", className: "border-red-700/60 bg-red-900/20 text-red-300" };
    case "feature-required":
      return { label: "feature required", className: "border-amber-600/40 bg-amber-900/20 text-amber-300" };
    case "live-validation-optional":
      return { label: "live optional", className: "border-sky-700/40 bg-sky-900/20 text-sky-300" };
    case "local-operator-context":
      return { label: "operator context", className: "border-border/80 bg-black/25 text-muted" };
    default:
      return { label: level || "unclassified", className: "border-border/80 bg-black/25 text-muted" };
  }
}

function settingsClassificationLabel(kind?: string) {
  switch (kind) {
    case "runtime-auth": return "runtime auth";
    case "provider-credential": return "provider credential";
    case "integration-credential": return "integration credential";
    case "oauth-config": return "oauth config";
    case "live-validation-target": return "live validation target";
    case "operator-context": return "operator context";
    default: return kind || "";
  }
}

function SettingsCriticalityChip({ level }: { level?: string }) {
  const meta = settingsCriticalityMeta(level);
  return <span className={`status-chip ${meta.className}`}>{meta.label}</span>;
}

function SettingsMetaLine({ criticality, classification, requiredWhen, usedBy }: {
  criticality?: string; classification?: string; requiredWhen?: string; usedBy?: string[];
}) {
  const classificationText = settingsClassificationLabel(classification);
  const usedByText = usedBy?.length ? usedBy.join(", ") : "";
  return (
    <div className="mt-2 space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <SettingsCriticalityChip level={criticality} />
        {classificationText && <span className="status-chip border-border/80 bg-black/25 text-muted">{classificationText}</span>}
      </div>
      {requiredWhen && <p className="text-[11px] leading-5 text-amber-100/45">{requiredWhen}</p>}
      {usedByText && <p className="text-[11px] leading-5 text-amber-100/32">used by: {usedByText}</p>}
    </div>
  );
}

function SettingsStatusBadge({ active, configured }: { active: boolean; configured: boolean }) {
  if (active) return <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">active</span>;
  if (configured) return <span className="status-chip border-amber-600/40 bg-amber-900/20 text-amber-400">configured</span>;
  return <span className="status-chip border-border/80 bg-black/25 text-muted">missing</span>;
}

function SettingsRuntimeBadge({ configured, configuredCount, fieldCount }: {
  configured: boolean; configuredCount: number; fieldCount: number;
}) {
  if (configuredCount === fieldCount && fieldCount > 0) return <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">ready</span>;
  if (configured) return <span className="status-chip border-amber-600/40 bg-amber-900/20 text-amber-400">partial</span>;
  return <span className="status-chip border-border/80 bg-black/25 text-muted">missing</span>;
}

function SettingsProviderCard({ provider, onSaved }: { provider: SettingsProviderStatus; onSaved: () => void | Promise<void> }) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saveState, setSaveState] = useState<SettingsSaveState>("idle");
  const [message, setMessage] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const selectedAuthMode = provider.auth_mode_env && drafts[provider.auth_mode_env] !== undefined ? drafts[provider.auth_mode_env] : provider.auth_mode;

  const settle = (nextState: SettingsSaveState, nextMessage: string) => {
    setSaveState(nextState); setMessage(nextMessage);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => { setSaveState("idle"); setMessage(""); }, 5000);
  };
  const setField = (env: string, value: string) => { setDrafts((prev) => ({ ...prev, [env]: value })); setSaveState("idle"); setMessage(""); };
  const clearDraftField = (env: string) => {
    setDrafts((prev) => { if (!(env in prev)) return prev; const next = { ...prev }; delete next[env]; return next; });
    setSaveState("idle"); setMessage("");
  };

  const save = async () => {
    const keys: Record<string, string> = {};
    const visibleFields = provider.fields.filter((field) => { if (!field.auth_modes?.length) return true; return !!selectedAuthMode && field.auth_modes.includes(selectedAuthMode); });
    for (const field of visibleFields) { const val = drafts[field.env]; if (val !== undefined && val !== "") keys[field.env] = val; }
    if (provider.toggle_env && drafts[provider.toggle_env] !== undefined) keys[provider.toggle_env] = drafts[provider.toggle_env];
    if (provider.auth_mode_env && drafts[provider.auth_mode_env] !== undefined) keys[provider.auth_mode_env] = drafts[provider.auth_mode_env];
    if (Object.keys(keys).length === 0) { setMessage("Aucune valeur a sauvegarder"); setSaveState("error"); return; }
    setSaveState("saving");
    try {
      const res = await put<SettingsProviderMutationResponse>(`/api/agents/providers/${provider.name}/key`, { keys });
      setSaveState("ok");
      setMessage(res.active ? (res.restarted_services?.length ? `Provider actif, restart: ${res.restarted_services.join(", ")}` : "Provider actif") : res.message || "Sauvegarde mais pas actif");
      setDrafts({}); await onSaved();
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => { setSaveState("idle"); setMessage(""); }, 4000);
    } catch (err) { setSaveState("error"); setMessage(err instanceof Error ? err.message : "Erreur"); }
  };

  const clearProvider = async (fields?: string[], scopeLabel?: string) => {
    if (fields?.length === 1) {
      const [fieldEnv] = fields;
      const field = provider.fields.find((entry) => entry.env === fieldEnv);
      if (field && !field.configured && drafts[fieldEnv] !== undefined) { clearDraftField(fieldEnv); settle("ok", `${field.label} efface du brouillon`); return; }
    }
    setSaveState("saving");
    try {
      const res = await post<SettingsProviderMutationResponse>(`/api/agents/providers/${provider.name}/clear`, fields?.length ? { fields } : undefined);
      if (fields?.length) { setDrafts((prev) => { const next = { ...prev }; for (const field of fields) delete next[field]; return next; }); } else setDrafts({});
      await onSaved();
      settle("ok", res.restarted_services?.length ? `${scopeLabel || "Valeurs"} efface${fields?.length === 1 ? "e" : "es"}, restart: ${res.restarted_services.join(", ")}` : res.message || `${scopeLabel || "Valeurs"} efface${fields?.length === 1 ? "e" : "es"}`);
    } catch (err) { setSaveState("error"); setMessage(err instanceof Error ? err.message : "Erreur"); }
  };

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  const visibleFields = provider.fields.filter((field) => { if (!field.auth_modes?.length) return true; return !!selectedAuthMode && field.auth_modes.includes(selectedAuthMode); });
  const hasDraft = visibleFields.some((field) => drafts[field.env]?.trim()) || (!!provider.auth_mode_env && drafts[provider.auth_mode_env] !== undefined) || (!!provider.toggle_env && drafts[provider.toggle_env] !== undefined);
  const canClear = provider.active || provider.configured || (provider.enabled ?? false) || provider.fields.some((field) => field.configured);

  return (
    <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold uppercase tracking-[0.18em] text-accent">{provider.label}</p>
          <SettingsMetaLine criticality={provider.criticality} classification={provider.classification} requiredWhen={provider.required_when} usedBy={provider.used_by} />
          {provider.default_model && <p className="mt-1 text-[11px] text-amber-100/45">{provider.default_model}</p>}
        </div>
        <SettingsStatusBadge active={provider.active} configured={provider.configured} />
      </div>
      <div className="space-y-3">
        {visibleFields.map((field) => (
          <div key={field.env}>
            <label className="mb-1.5 flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-muted">
              <span>{field.label}</span>
              <span className="normal-case tracking-normal text-amber-100/35">{field.env}</span>
            </label>
            <input type={field.secret ? "password" : "text"} placeholder={field.configured ? field.hint : "Non configure"} value={drafts[field.env] ?? ""} onChange={(e) => setField(field.env, e.target.value)} className="w-full rounded-2xl border border-border/80 bg-black/35 px-3 py-2.5 text-sm text-amber-100 outline-none transition placeholder:text-amber-100/25 focus:border-accent/50" />
          </div>
        ))}
        {provider.toggle_env !== undefined && (
          <label className="flex cursor-pointer items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted">
            <input type="checkbox" checked={drafts[provider.toggle_env] !== undefined ? drafts[provider.toggle_env] === "true" : provider.enabled ?? false} onChange={(e) => setField(provider.toggle_env!, e.target.checked ? "true" : "false")} className="accent-accent" />
            Activer
          </label>
        )}
      </div>
      <div className="mt-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          {message && <p className={["text-[12px]", saveState === "ok" ? "text-emerald-400" : "text-red-400"].join(" ")}>{message}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" disabled={!canClear || saveState === "saving"} onClick={() => clearProvider()} className="rounded-2xl border border-red-800/50 bg-red-900/10 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-red-300 transition hover:border-red-700/60 hover:bg-red-900/20 disabled:cursor-not-allowed disabled:opacity-40">clear</button>
          <button type="button" disabled={(!hasDraft && !Object.keys(drafts).length) || saveState === "saving"} onClick={save} className="rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-accent transition hover:border-accent/50 hover:bg-accent/18 disabled:cursor-not-allowed disabled:opacity-40">{saveState === "saving" ? "..." : "save"}</button>
        </div>
      </div>
    </div>
  );
}

function SettingsRuntimeSecretCard({ group, onSaved }: { group: SettingsRuntimeSecretGroupStatus; onSaved: () => Promise<void> }) {
  const { login, logout } = useAuth();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saveState, setSaveState] = useState<SettingsSaveState>("idle");
  const [message, setMessage] = useState("");
  const [generatedValue, setGeneratedValue] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const selectedProvider = group.provider_env && drafts[group.provider_env] !== undefined ? drafts[group.provider_env] : group.provider;
  const selectedAuthMode = group.auth_mode_env && drafts[group.auth_mode_env] !== undefined ? drafts[group.auth_mode_env] : group.auth_mode;

  const setField = (env: string, value: string) => { setDrafts((prev) => ({ ...prev, [env]: value })); setSaveState("idle"); setMessage(""); };
  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  const settle = (nextState: SettingsSaveState, nextMessage: string) => {
    setSaveState(nextState); setMessage(nextMessage);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => { setSaveState("idle"); setMessage(""); }, 5000);
  };

  const syncAuthIfNeeded = useCallback(async (response: SettingsRuntimeSecretMutationResponse) => {
    const token = response.client_token || response.generated_value;
    if (!token) return;
    const ok = await login(token, isPersisted());
    if (!ok) throw new Error("Rotation de la cle appliquee, mais re-authentification impossible");
  }, [login]);

  const save = async () => {
    const values: Record<string, string> = {};
    const visibleFields = group.fields.filter((field) => {
      if (field.providers?.length) { if (!selectedProvider || !field.providers.includes(selectedProvider)) return false; }
      if (!field.auth_modes?.length) return true;
      return !!selectedAuthMode && field.auth_modes.includes(selectedAuthMode);
    });
    for (const field of visibleFields) { const value = drafts[field.env]; if (value !== undefined && value !== "") values[field.env] = value; }
    if (group.provider_env && drafts[group.provider_env] !== undefined) values[group.provider_env] = drafts[group.provider_env];
    if (group.auth_mode_env && drafts[group.auth_mode_env] !== undefined) values[group.auth_mode_env] = drafts[group.auth_mode_env];
    if (Object.keys(values).length === 0) { settle("error", "Aucune valeur a sauvegarder"); return; }
    setSaveState("saving");
    try {
      const response = await put<SettingsRuntimeSecretMutationResponse>(`/api/settings/runtime-secrets/${group.name}`, { values });
      if (group.name === "auth") await syncAuthIfNeeded(response);
      setDrafts({}); setGeneratedValue(""); await onSaved();
      settle("ok", response.restarted_services?.length ? `Sauvegarde appliquee, restart: ${response.restarted_services.join(", ")}` : response.message || "Sauvegarde appliquee");
    } catch (error) { settle("error", error instanceof Error ? error.message : "Erreur"); }
  };

  const clearGroup = async () => {
    setSaveState("saving");
    try {
      const response = await post<SettingsRuntimeSecretMutationResponse>(`/api/settings/runtime-secrets/${group.name}/clear`);
      if (group.name === "auth") logout();
      setDrafts({}); setGeneratedValue(""); await onSaved();
      settle("ok", response.restarted_services?.length ? `Valeurs effacees, restart: ${response.restarted_services.join(", ")}` : response.message || "Valeurs effacees");
    } catch (error) { settle("error", error instanceof Error ? error.message : "Erreur"); }
  };

  const generate = async () => {
    setSaveState("saving");
    try {
      const response = await post<SettingsRuntimeSecretMutationResponse>(`/api/settings/runtime-secrets/${group.name}/generate`);
      await syncAuthIfNeeded(response);
      setGeneratedValue(response.generated_value || ""); setDrafts({}); await onSaved();
      settle("ok", response.restarted_services?.length ? `Nouvelle cle generee, restart: ${response.restarted_services.join(", ")}` : response.message || "Nouvelle cle generee");
    } catch (error) { settle("error", error instanceof Error ? error.message : "Erreur"); }
  };

  const visibleFields = group.fields.filter((field) => {
    if (field.providers?.length) { if (!selectedProvider || !field.providers.includes(selectedProvider)) return false; }
    if (!field.auth_modes?.length) return true;
    return !!selectedAuthMode && field.auth_modes.includes(selectedAuthMode);
  });
  const hasDraft = visibleFields.some((field) => (drafts[field.env] || "").trim().length > 0) || (!!group.provider_env && drafts[group.provider_env] !== undefined) || (!!group.auth_mode_env && drafts[group.auth_mode_env] !== undefined);

  return (
    <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold uppercase tracking-[0.18em] text-accent">{group.label}</p>
          <p className="mt-1 text-[12px] leading-5 text-amber-100/48">{group.description}</p>
          <SettingsMetaLine criticality={group.criticality} classification={group.classification} requiredWhen={group.required_when} usedBy={group.used_by} />
        </div>
        <SettingsRuntimeBadge configured={group.configured} configuredCount={group.configured_count} fieldCount={group.field_count} />
      </div>
      <div className="space-y-3">
        {group.provider_env && group.providers && group.providers.length > 1 && (
          <div>
            <label className="mb-1.5 flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-muted"><span>Provider</span><span className="normal-case tracking-normal text-amber-100/35">{group.provider_env}</span></label>
            <select value={selectedProvider ?? group.providers[0]} onChange={(e) => setField(group.provider_env!, e.target.value)} className="w-full rounded-2xl border border-border/80 bg-black/35 px-3 py-2.5 text-sm text-amber-100 outline-none transition focus:border-accent/50">
              {group.providers.map((provider) => <option key={provider} value={provider} className="bg-[#0a0a0a]">{provider}</option>)}
            </select>
          </div>
        )}
        {visibleFields.map((field) => (
          <div key={field.env}>
            <label className="mb-1.5 flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-muted"><span>{field.label}</span><span className="normal-case tracking-normal text-amber-100/35">{field.env}</span></label>
            <input type={field.secret ? "password" : "text"} placeholder={field.configured ? field.hint : "Non configure"} value={drafts[field.env] ?? ""} onChange={(e) => setField(field.env, e.target.value)} className="w-full rounded-2xl border border-border/80 bg-black/35 px-3 py-2.5 text-sm text-amber-100 outline-none transition placeholder:text-amber-100/25 focus:border-accent/50" />
            {field.restart_services.length > 0 && <p className="mt-1 text-[11px] text-amber-100/35">restart: {field.restart_services.join(", ")}</p>}
          </div>
        ))}
      </div>
      {generatedValue && (
        <div className="mt-4 rounded-2xl border border-[#214e31] bg-[#0c170f]/80 p-3">
          <p className="text-[11px] uppercase tracking-[0.16em] text-[#8cffb7]">generated value</p>
          <code className="mt-2 block overflow-x-auto whitespace-pre-wrap break-all text-[12px] text-[#c9ffd8]">{generatedValue}</code>
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          {message && <p className={["text-[12px]", saveState === "ok" ? "text-emerald-400" : "text-red-400"].join(" ")}>{message}</p>}
          {group.restart_services.length > 0 && <p className="text-[11px] text-amber-100/35">redemarrage pilote: {group.restart_services.join(", ")}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {group.generate_supported && (
            <button type="button" disabled={saveState === "saving"} onClick={generate} className="rounded-2xl border border-[#214e31] bg-[#0c170f]/80 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-[#8cffb7] transition hover:border-[#2d6942] hover:bg-[#0f2116] disabled:cursor-not-allowed disabled:opacity-40">generate</button>
          )}
          <button type="button" disabled={saveState === "saving" || !group.configured} onClick={clearGroup} className="rounded-2xl border border-red-800/50 bg-red-900/10 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-red-300 transition hover:border-red-700/60 hover:bg-red-900/20 disabled:cursor-not-allowed disabled:opacity-40">clear</button>
          <button type="button" disabled={!hasDraft || saveState === "saving"} onClick={save} className="rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-[11px] uppercase tracking-[0.16em] text-accent transition hover:border-accent/50 hover:bg-accent/18 disabled:cursor-not-allowed disabled:opacity-40">{saveState === "saving" ? "..." : "save"}</button>
        </div>
      </div>
    </div>
  );
}

function SettingsContent() {
  const [providers, setProviders] = useState<SettingsProviderStatus[]>([]);
  const [runtimeGroups, setRuntimeGroups] = useState<SettingsRuntimeSecretGroupStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const [providerResponse, runtimeResponse] = await Promise.all([
        get<{ providers: SettingsProviderStatus[] }>("/api/agents/providers/status"),
        get<{ groups: SettingsRuntimeSecretGroupStatus[] }>("/api/settings/runtime-secrets"),
      ]);
      setProviders(providerResponse.providers);
      setRuntimeGroups(runtimeResponse.groups);
      setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "Erreur de chargement"); } finally { setLoading(false); }
  }, []);

  useEffect(() => { void fetchStatus(); }, [fetchStatus]);

  const active = providers.filter((p) => p.active);
  const inactive = providers.filter((p) => !p.active);
  const runtimeReady = runtimeGroups.filter((group) => group.configured);
  const runtimeMissing = runtimeGroups.filter((group) => !group.configured);
  const runtimeSecurityGroups = runtimeGroups.filter((group) => group.criticality === "required-security");
  const runtimeIntegrationGroups = runtimeGroups.filter((group) => group.criticality !== "required-security");

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-[1.4rem] border border-accent/18 bg-accent/5 p-5">
          <p className="screen-label">provider administration</p>
          <p className="mt-2 text-[12px] leading-5 text-amber-100/58">
            Configuration des cles API pour chaque provider LLM.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">{active.length} actif{active.length > 1 ? "s" : ""}</span>
            <span className="status-chip border-border/80 bg-black/25 text-muted">{inactive.length} non configure{inactive.length > 1 ? "s" : ""}</span>
          </div>
        </div>
        <div className="rounded-[1.4rem] border border-accent/18 bg-accent/5 p-5">
          <p className="screen-label">runtime security + integrations</p>
          <p className="mt-2 text-[12px] leading-5 text-amber-100/58">
            Secrets runtime, securite et integrations optionnelles.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">{runtimeReady.length} configure{runtimeReady.length > 1 ? "s" : ""}</span>
            <span className="status-chip border-border/80 bg-black/25 text-muted">{runtimeMissing.length} incomplet{runtimeMissing.length > 1 ? "s" : ""}</span>
          </div>
        </div>
      </div>

      {loading && <p className="text-center text-sm text-muted">Chargement...</p>}
      {error && <div className="rounded-2xl border border-red-800/60 bg-red-900/15 p-4 text-[12px] text-red-400">{error}</div>}

      {runtimeSecurityGroups.length > 0 && (
        <section>
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">Security runtime</h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {runtimeSecurityGroups.map((group) => <SettingsRuntimeSecretCard key={group.name} group={group} onSaved={fetchStatus} />)}
          </div>
        </section>
      )}

      {runtimeIntegrationGroups.length > 0 && (
        <section>
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">Integrations runtime</h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {runtimeIntegrationGroups.map((group) => <SettingsRuntimeSecretCard key={group.name} group={group} onSaved={fetchStatus} />)}
          </div>
        </section>
      )}

      {active.length > 0 && (
        <section>
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">Providers actifs</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {active.map((provider) => <SettingsProviderCard key={provider.name} provider={provider} onSaved={() => void fetchStatus()} />)}
          </div>
        </section>
      )}

      {inactive.length > 0 && (
        <section>
          <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">Providers disponibles</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {inactive.map((provider) => <SettingsProviderCard key={provider.name} provider={provider} onSaved={() => void fetchStatus()} />)}
          </div>
        </section>
      )}
    </div>
  );
}

/* ================================================================== */
/*  MCP tab content (merged from McpServers.tsx)                       */
/* ================================================================== */

type McpTool = { name: string; description?: string };

type McpServer = {
  name: string;
  description?: string;
  tools_count?: number;
  tools?: McpTool[];
  status?: "connected" | "disconnected" | "unknown";
  url?: string;
  doc_url?: string;
};

type McpSummary = { servers?: McpServer[] };

const MCP_FALLBACK_SERVERS: McpServer[] = [
  { name: "Seeed KiCad MCP", description: "Seeed Studio component library and footprint resolution for KiCad.", tools_count: 12, status: "unknown", url: "https://mcp-kicad-seeed.saillant.cc", doc_url: "https://github.com/Seeed-Studio/kicad-mcp" },
  { name: "circuit-synth", description: "Circuit synthesis and netlist generation from natural language descriptions.", tools_count: 8, status: "unknown", url: "https://mcp-circuit-synth.saillant.cc" },
  { name: "kicad-happy", description: "KiCad project management, schematic editing and DRC automation.", tools_count: 15, status: "unknown", url: "https://mcp-kicad-happy.saillant.cc" },
  { name: "mixelpixx", description: "PCB layout assistance, component placement and routing suggestions.", tools_count: 10, status: "unknown", url: "https://mcp-mixelpixx.saillant.cc" },
  { name: "SPICEBridge", description: "SPICE simulation bridge: run ngspice/LTspice from MCP tool calls.", tools_count: 6, status: "unknown", url: "https://mcp-spicebridge.saillant.cc" },
];

function mcpStatusBadge(status?: string) {
  if (status === "connected") return <Badge color="accent">connected</Badge>;
  if (status === "disconnected") return <Badge color="error">disconnected</Badge>;
  return <Badge color="muted">unknown</Badge>;
}

function McpServerCard({ server, onPing, pinging }: { server: McpServer; onPing: (name: string) => void; pinging: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const tools = server.tools ?? [];

  return (
    <div className="rounded-3xl border border-border/80 bg-black/20 p-5 transition-all duration-200 hover:border-accent/22">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-[14px] font-semibold uppercase tracking-[0.14em] text-accent">{server.name}</h3>
          {server.description && <p className="mt-1 text-xs leading-5 text-amber-100/55">{server.description}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">{mcpStatusBadge(server.status)}</div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Badge color="muted">{server.tools_count ?? tools.length} tools</Badge>
        {server.url && <span className="text-[10px] font-mono text-amber-50/35 tracking-wider truncate max-w-[260px]">{server.url.replace(/^https?:\/\//, "")}</span>}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button onClick={() => onPing(server.name)} disabled={pinging} className="inline-flex min-h-8 items-center rounded-full border border-accent/35 bg-accent/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-accent transition-colors hover:bg-accent/20 disabled:opacity-40">{pinging ? "pinging..." : "ping"}</button>
        {tools.length > 0 && <button onClick={() => setExpanded(!expanded)} className="inline-flex min-h-8 items-center rounded-full border border-border/80 bg-black/25 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted transition-colors hover:text-accent">{expanded ? "hide tools" : "show tools"}</button>}
        {server.doc_url && <a href={server.doc_url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-8 items-center rounded-full border border-border/80 bg-black/25 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted transition-colors hover:text-accent">docs</a>}
      </div>
      {expanded && tools.length > 0 && (
        <div className="mt-4 space-y-1 rounded-2xl border border-border/60 bg-black/30 p-3">
          {tools.map((tool) => (
            <div key={tool.name} className="flex items-baseline gap-2 py-1">
              <span className="text-[11px] font-mono font-semibold text-accent/80">{tool.name}</span>
              {tool.description && <span className="text-[10px] text-amber-50/40 truncate">{tool.description}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function McpContent() {
  const { data, loading, error } = useFetch<McpSummary>("/api/ops/mcp/summary", { pollIntervalMs: 30_000 });
  const [pingStates, setPingStates] = useState<Record<string, "pinging" | "ok" | "fail">>({});

  const handlePing = useCallback(async (name: string) => {
    setPingStates((prev) => ({ ...prev, [name]: "pinging" }));
    try { await post("/api/ops/mcp/ping", { server: name }); setPingStates((prev) => ({ ...prev, [name]: "ok" })); } catch { setPingStates((prev) => ({ ...prev, [name]: "fail" })); }
    setTimeout(() => { setPingStates((prev) => { const next = { ...prev }; delete next[name]; return next; }); }, 3000);
  }, []);

  const servers: McpServer[] = data?.servers && data.servers.length > 0 ? data.servers : MCP_FALLBACK_SERVERS;
  const connected = servers.filter((s) => s.status === "connected").length;
  const totalTools = servers.reduce((sum, s) => sum + (s.tools_count ?? s.tools?.length ?? 0), 0);

  if (loading && !data) {
    return <LoadingPanel title="Loading MCP servers" message="Fetching MCP server registry and tool inventory." />;
  }

  return (
    <div className="space-y-6">
      <Card title="MCP Servers">
        <p className="text-sm leading-7 text-amber-100/60">Serveurs Model Context Protocol integres a Mascarade.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge color="accent">{servers.length} servers</Badge>
          <Badge color={connected > 0 ? "accent" : "muted"}>{connected} connected</Badge>
          <Badge color="muted">{totalTools} tools</Badge>
        </div>
      </Card>
      {error && !data && <InlineNotice title="mcp registry unavailable" message={error} tone="error" className="mx-auto max-w-3xl" />}
      {error && data && <InlineNotice title="refresh note" message={`Refresh warning: ${error}`} tone="info" />}
      <Card title="Server Registry">
        <div className="mt-2 space-y-4">
          {servers.map((server) => <McpServerCard key={server.name} server={server} onPing={handlePing} pinging={pingStates[server.name] === "pinging"} />)}
        </div>
      </Card>
    </div>
  );
}

/* ================================================================== */
/*  Main export with tabs                                              */
/* ================================================================== */

const ADMIN_TABS = ["control", "fleet", "settings", "mcp"] as const;

export default function Administration() {
  const [tab, setTab] = useState<string>("control");

  return (
    <div className="space-y-6">
      <div className="flex gap-1 mb-6">
        {ADMIN_TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-2xl text-xs uppercase tracking-[0.16em] transition ${
              tab === t
                ? "bg-accent/15 text-accent border border-accent/30"
                : "bg-black/30 text-muted border border-border/50 hover:text-accent"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "control" && <ControlContent />}
      {tab === "fleet" && <FleetContent />}
      {tab === "settings" && <SettingsContent />}
      {tab === "mcp" && <McpContent />}
    </div>
  );
}

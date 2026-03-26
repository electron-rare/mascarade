import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import Shell from "./components/layout/Shell";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Playground = lazy(() => import("./pages/Playground"));
const Agents = lazy(() => import("./pages/Agents"));
const AgentDetail = lazy(() => import("./pages/AgentDetail"));
const Orchestrate = lazy(() => import("./pages/Orchestrate"));
const OpsHub = lazy(() => import("./pages/OpsHub"));
const Logs = lazy(() => import("./pages/Logs"));
const Metrics = lazy(() => import("./pages/Metrics"));
const Infrastructure = lazy(() => import("./pages/Infrastructure"));
const KnowledgeBrowser = lazy(() => import("./pages/KnowledgeBrowser"));
const QdrantKnowledge = lazy(() => import("./pages/QdrantKnowledge"));
const ComfyUI = lazy(() => import("./pages/ComfyUI"));
const KillLifeWorkflows = lazy(() => import("./pages/KillLifeWorkflows"));
const KillLifeWorkflowEditor = lazy(() => import("./pages/KillLifeWorkflowEditor"));
const Settings = lazy(() => import("./pages/Settings"));
const P2PMesh = lazy(() => import("./pages/P2PMesh"));
const FineTuning = lazy(() => import("./pages/FineTuning"));
const Calendar = lazy(() => import("./pages/Calendar"));
const Mail = lazy(() => import("./pages/Mail"));
const McpServers = lazy(() => import("./pages/McpServers"));

function PageSpinner() {
  return (
    <div className="flex items-center justify-center" style={{ minHeight: "60vh" }}>
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-[rgba(0,0,0,0.1)] border-t-[#0071e3]" />
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageSpinner />}>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Dashboard />} />
            <Route path="playground" element={<Playground />} />
            <Route path="agents" element={<Agents />} />
            <Route path="agents/:name" element={<AgentDetail />} />
            <Route path="orchestrate" element={<Orchestrate />} />
            <Route path="ops" element={<OpsHub />} />
            <Route path="logs" element={<Logs />} />
            <Route path="metrics" element={<Metrics />} />
            <Route path="infra" element={<Infrastructure />} />
            <Route path="knowledge-base" element={<KnowledgeBrowser />} />
            <Route path="qdrant-knowledge" element={<QdrantKnowledge />} />
            <Route path="comfyui" element={<ComfyUI />} />
            <Route path="kill-life" element={<KillLifeWorkflows />} />
            <Route path="kill-life/:workflowId" element={<KillLifeWorkflowEditor />} />
            <Route path="settings" element={<Settings />} />
            <Route path="p2p" element={<P2PMesh />} />
            <Route path="finetune" element={<FineTuning />} />
            <Route path="calendar" element={<Calendar />} />
            <Route path="mail" element={<Mail />} />
            <Route path="mcp" element={<McpServers />} />
            <Route path="*" element={<p className="text-[#ff3b30] text-sm text-center mt-20">404 — page introuvable</p>} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}

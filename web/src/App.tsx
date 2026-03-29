import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import Shell from "./components/layout/Shell";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Playground = lazy(() => import("./pages/Playground"));
const Agents = lazy(() => import("./pages/Agents"));
const AgentDetail = lazy(() => import("./pages/AgentDetail"));
const Orchestrate = lazy(() => import("./pages/Orchestrate"));
const Administration = lazy(() => import("./pages/Administration"));
const Knowledge = lazy(() => import("./pages/Knowledge"));
const Pipeline = lazy(() => import("./pages/Pipeline"));
const Training = lazy(() => import("./pages/Training"));
const KillLifeWorkflows = lazy(() => import("./pages/KillLifeWorkflows"));
const KillLifeWorkflowEditor = lazy(() => import("./pages/KillLifeWorkflowEditor"));
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

function LegacyRedirect({ to }: { to: string }) {
  const location = useLocation();

  return <Navigate replace to={{ pathname: to, search: location.search, hash: location.hash }} />;
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
            <Route path="admin" element={<Administration />} />
            <Route path="knowledge" element={<Knowledge />} />
            <Route path="pipeline" element={<Pipeline />} />
            <Route path="training" element={<Training />} />
            <Route path="kill-life" element={<KillLifeWorkflows />} />
            <Route path="kill-life/:workflowId" element={<KillLifeWorkflowEditor />} />
            <Route path="calendar" element={<Calendar />} />
            <Route path="mail" element={<Mail />} />
            <Route path="mcp" element={<McpServers />} />
            <Route path="ops" element={<LegacyRedirect to="/admin" />} />
            <Route path="logs" element={<LegacyRedirect to="/admin" />} />
            <Route path="metrics" element={<LegacyRedirect to="/admin" />} />
            <Route path="infra" element={<LegacyRedirect to="/admin" />} />
            <Route path="settings" element={<LegacyRedirect to="/admin" />} />
            <Route path="p2p" element={<LegacyRedirect to="/admin" />} />
            <Route path="comfyui" element={<LegacyRedirect to="/admin" />} />
            <Route path="knowledge-base" element={<LegacyRedirect to="/knowledge" />} />
            <Route path="qdrant-knowledge" element={<LegacyRedirect to="/knowledge" />} />
            <Route path="finetune" element={<LegacyRedirect to="/training" />} />
            <Route path="*" element={<p className="text-[#ff3b30] text-sm text-center mt-20">404 — page introuvable</p>} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}

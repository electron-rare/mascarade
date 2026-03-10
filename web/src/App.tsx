import { Routes, Route } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import Shell from "./components/layout/Shell";
import Dashboard from "./pages/Dashboard";
import Playground from "./pages/Playground";
import Agents from "./pages/Agents";
import AgentDetail from "./pages/AgentDetail";
import Orchestrate from "./pages/Orchestrate";
import OpsHub from "./pages/OpsHub";
import Logs from "./pages/Logs";
import Metrics from "./pages/Metrics";
import Infrastructure from "./pages/Infrastructure";
import KnowledgeBrowser from "./pages/KnowledgeBrowser";
import ComfyUI from "./pages/ComfyUI";
import KillLifeWorkflows from "./pages/KillLifeWorkflows";
import KillLifeWorkflowEditor from "./pages/KillLifeWorkflowEditor";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <ErrorBoundary>
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
          <Route path="comfyui" element={<ComfyUI />} />
          <Route path="kill-life" element={<KillLifeWorkflows />} />
          <Route path="kill-life/:workflowId" element={<KillLifeWorkflowEditor />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<p className="text-error text-sm text-center mt-20">404 — page not found</p>} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}

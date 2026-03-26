import { Routes, Route } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import Shell from "./components/layout/Shell";
import Dashboard from "./pages/Dashboard";
import Playground from "./pages/Playground";
import Agents from "./pages/Agents";
import AgentDetail from "./pages/AgentDetail";
import Training from "./pages/Training";
import Knowledge from "./pages/Knowledge";
import Administration from "./pages/Administration";
import Pipeline from "./pages/Pipeline";
import KillLifeWorkflows from "./pages/KillLifeWorkflows";
import KillLifeWorkflowEditor from "./pages/KillLifeWorkflowEditor";

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Dashboard />} />
          <Route path="playground" element={<Playground />} />
          <Route path="agents" element={<Agents />} />
          <Route path="agents/:name" element={<AgentDetail />} />
          <Route path="training" element={<Training />} />
          <Route path="knowledge" element={<Knowledge />} />
          <Route path="pipeline" element={<Pipeline />} />
          <Route path="admin" element={<Administration />} />
          <Route path="kill-life" element={<KillLifeWorkflows />} />
          <Route path="kill-life/:workflowId" element={<KillLifeWorkflowEditor />} />
          <Route path="*" element={<p className="text-error text-sm text-center mt-20">404 — page not found</p>} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}

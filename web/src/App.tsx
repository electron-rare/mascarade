import { Routes, Route } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import Shell from "./components/layout/Shell";
import Dashboard from "./pages/Dashboard";
import Playground from "./pages/Playground";
import Agents from "./pages/Agents";
import AgentDetail from "./pages/AgentDetail";
import Orchestrate from "./pages/Orchestrate";
import Logs from "./pages/Logs";
import Metrics from "./pages/Metrics";
import Infrastructure from "./pages/Infrastructure";
import NotionBrowser from "./pages/NotionBrowser";
import ComfyUI from "./pages/ComfyUI";

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
          <Route path="logs" element={<Logs />} />
          <Route path="metrics" element={<Metrics />} />
          <Route path="infra" element={<Infrastructure />} />
          <Route path="notion" element={<NotionBrowser />} />
          <Route path="comfyui" element={<ComfyUI />} />
          <Route path="*" element={<p className="text-error text-sm text-center mt-20">404 — page not found</p>} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}

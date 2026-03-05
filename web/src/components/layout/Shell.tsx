import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

const titles: Record<string, string> = {
  "/": "Dashboard",
  "/playground": "Playground",
  "/agents": "Agents",
  "/orchestrate": "Orchestrate",
  "/metrics": "Metrics",
  "/infra": "Infrastructure",
  "/notion": "Notion Browser",
  "/comfyui": "ComfyUI",
};

export default function Shell() {
  const { pathname } = useLocation();
  const title =
    titles[pathname] ||
    (pathname.startsWith("/agents/")
      ? `Agent — ${pathname.split("/").pop()}`
      : "Mascarade");

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar title={title} />
        <main className="flex-1 overflow-y-auto p-5">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

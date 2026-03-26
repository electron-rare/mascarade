import { Hono } from "hono";
import { monitorRoutes } from "./ops/monitor.js";
import { mcpRoutes } from "./ops/mcp.js";
import { agentTracesRoutes } from "./ops/agentTraces.js";
import { logsRoutes } from "./ops/logs.js";
import { frappeRoutes } from "./ops/frappe.js";
import { calendarRoutes } from "./ops/calendar.js";
import { mailRoutes } from "./ops/mail.js";

// Re-export public API used by tests
export { decodeLokiLine, lokiValueToOpsLogEntry } from "./ops/_shared.js";

const ops = new Hono();

ops.route("/", monitorRoutes);
ops.route("/", mcpRoutes);
ops.route("/", agentTracesRoutes);
ops.route("/", logsRoutes);
ops.route("/", frappeRoutes);
ops.route("/", calendarRoutes);
ops.route("/", mailRoutes);

export { ops };

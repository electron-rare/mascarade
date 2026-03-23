import { Hono } from "hono";
import { handleCoreError } from "../../middleware/error.js";
import {
  getNumberParam,
  proxySseResponse,
  coreClient,
  getCoreAuthHeaders,
  CORE_URL,
} from "./_shared.js";

const agentTracesRoutes = new Hono();

agentTracesRoutes.get("/agent-traces/recent", async (c) => {
  try {
    const query = c.req.query();
    const result = await coreClient.recentAgentTraces({
      limit: getNumberParam(query.limit, 50, 500),
      run_id: query.run_id,
      agent_name: query.agent_name,
      event_type: query.event_type,
    });
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

agentTracesRoutes.get("/agent-traces/stream", async (c) => {
  try {
    const search = new URL(c.req.url).search;
    return await proxySseResponse(
      `${CORE_URL}/agent-traces/stream${search}`,
      getCoreAuthHeaders(),
      c.req.raw.signal,
    );
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

agentTracesRoutes.get("/agent-traces/:runId", async (c) => {
  try {
    const runId = c.req.param("runId");
    const limit = getNumberParam(c.req.query("limit"), 200, 1000);
    const result = await coreClient.runAgentTraces(runId, limit);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { agentTracesRoutes };

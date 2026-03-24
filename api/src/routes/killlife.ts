import { Hono } from "hono";
import {
  getWorkflow,
  listEvidence,
  listWorkflowRuns,
  listWorkflows,
  runWorkflow,
  saveWorkflow,
  validateWorkflowDocument,
} from "../lib/killlife.js";
import { validate } from "../validation/index.js";
import { WorkflowRunRequestSchema, type WorkflowRunRequest } from "../validation/schemas.js";

const killlife = new Hono();

function badRequest(message: string) {
  return { error: message };
}

killlife.get("/workflows", async (c) => {
  try {
    const workflows = await listWorkflows();
    return c.json({
      root: process.env.KILL_LIFE_ROOT || "/home/clems/Kill_LIFE",
      workflows,
    });
  } catch (error) {
    return c.json({ error: error instanceof Error ? error.message : "Failed to list workflows" }, 500);
  }
});

killlife.get("/workflows/:id", async (c) => {
  try {
    const workflow = await getWorkflow(c.req.param("id"));
    const validation = validateWorkflowDocument(workflow);
    const runs = await listWorkflowRuns(workflow.id, 10);
    return c.json({ workflow, validation, runs });
  } catch (error) {
    return c.json({ error: error instanceof Error ? error.message : "Failed to load workflow" }, 404);
  }
});

killlife.put("/workflows/:id", async (c) => {
  try {
    const payload = await c.req.json();
    const result = await saveWorkflow(c.req.param("id"), payload);
    return c.json(result);
  } catch (error) {
    return c.json(
      badRequest(error instanceof Error ? error.message : "Failed to save workflow"),
      400,
    );
  }
});

killlife.post("/workflows/:id/validate", async (c) => {
  try {
    const payload = await c.req.json().catch(() => undefined);
    if (payload) {
      const validation = validateWorkflowDocument(payload);
      return c.json(validation);
    }
    const workflow = await getWorkflow(c.req.param("id"));
    const validation = validateWorkflowDocument(workflow);
    return c.json(validation);
  } catch (error) {
    return c.json(
      badRequest(error instanceof Error ? error.message : "Failed to validate workflow"),
      400,
    );
  }
});

killlife.post("/workflows/:id/run", validate(WorkflowRunRequestSchema), async (c) => {
  try {
    const body = c.get("validated" as never) as WorkflowRunRequest;
    const id = c.req.param("id");
    if (!id) return c.json(badRequest("Missing workflow id"), 400);
    const result = await runWorkflow(id, {
      mode: body.mode,
      dry_run: body.dry_run,
      inputs: body.inputs,
    });
    return c.json(result);
  } catch (error) {
    return c.json(
      badRequest(error instanceof Error ? error.message : "Failed to run workflow"),
      400,
    );
  }
});

killlife.get("/workflows/:id/runs", async (c) => {
  try {
    const runs = await listWorkflowRuns(c.req.param("id"), 20);
    return c.json({ runs });
  } catch (error) {
    return c.json(
      badRequest(error instanceof Error ? error.message : "Failed to list runs"),
      400,
    );
  }
});

killlife.get("/evidence/:target", async (c) => {
  try {
    const evidence = await listEvidence(c.req.param("target"));
    return c.json({ evidence });
  } catch (error) {
    return c.json(
      badRequest(error instanceof Error ? error.message : "Failed to list evidence"),
      400,
    );
  }
});

export { killlife };

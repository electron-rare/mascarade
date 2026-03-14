import { spawn } from "node:child_process";
import path from "node:path";
import { Hono, type Context } from "hono";
import { emitStructuredLog } from "../lib/otel.js";

const pipeline = new Hono();

const VALID_DOMAINS = [
  "stm32", "spice", "iot", "power", "dsp", "emc", "kicad",
  "embedded", "platformio", "freecad", "components"
];

/**
 * POST /run - Trigger pipeline execution
 * Body: { domain: string, dry_run?: boolean }
 * Returns: { status: string, run_id: string, domain: string, dry_run: boolean }
 */
pipeline.post("/run", async (c: Context) => {
  try {
    const body = await c.req.json();
    const domain = typeof body.domain === "string" ? body.domain.trim() : null;
    const dryRun = body.dry_run === true;

    // Validate domain
    if (!domain || !VALID_DOMAINS.includes(domain)) {
      emitStructuredLog({
        severity: "warning",
        source: "api",
        service: "pipeline",
        message: `Invalid domain requested: ${domain || "(missing)"}`,
      });
      return c.json(
        {
          error: "Invalid or missing domain parameter",
          valid_domains: VALID_DOMAINS,
        },
        400,
      );
    }

    // Generate run ID
    const runId = `pipeline-${domain}-${Date.now()}`;

    // Determine pipeline script path (relative to api/ directory)
    const pipelinePath = path.resolve(process.cwd(), "../finetune/pipeline_automated.py");

    // Build command args
    const args = [pipelinePath, domain];
    if (dryRun) {
      args.push("--dry-run");
    }

    // Spawn pipeline process in background
    const child = spawn("python3", args, {
      detached: true,
      stdio: "ignore",
    });

    // Detach the process so it continues after API exits
    child.unref();

    emitStructuredLog({
      severity: "info",
      source: "api",
      service: "pipeline",
      message: `Pipeline started for domain ${domain}${dryRun ? " (dry-run)" : ""}`,
      run_id: runId,
    });

    return c.json(
      {
        status: "started",
        run_id: runId,
        domain: domain,
        dry_run: dryRun,
      },
      200,
    );
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    emitStructuredLog({
      severity: "error",
      source: "api",
      service: "pipeline",
      message: `Failed to start pipeline: ${errorMsg}`,
    });
    return c.json({ error: "Failed to start pipeline", details: errorMsg }, 500);
  }
});

/**
 * GET /status - Check pipeline state
 * TODO: Implementation in subtask-4-3
 */
pipeline.get("/status", async (c: Context) => {
  return c.json({ status: "not_implemented" }, 501);
});

/**
 * GET /models - List fine-tuned models from registry
 * TODO: Implementation in subtask-4-4
 */
pipeline.get("/models", async (c: Context) => {
  return c.json({ status: "not_implemented" }, 501);
});

export { pipeline };

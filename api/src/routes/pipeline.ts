import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { Hono, type Context } from "hono";
import { emitStructuredLog } from "../lib/otel.js";
import { validate } from "../validation/index.js";
import { PipelineRunRequestSchema, type PipelineRunRequest } from "../validation/schemas.js";

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
pipeline.post("/run", validate(PipelineRunRequestSchema), async (c: Context) => {
  try {
    const body = c.get("validated" as never) as PipelineRunRequest;
    const domain = body.domain.trim();
    const dryRun = body.dry_run;

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
 * Returns: { ok: boolean, status: string, data?: object, error?: string }
 */
pipeline.get("/status", async (c: Context) => {
  try {
    // Determine state file path (relative to api/ directory)
    const statePath = path.resolve(process.cwd(), "../finetune/state.json");

    // Check if state file exists
    if (!existsSync(statePath)) {
      emitStructuredLog({
        severity: "info",
        source: "api",
        service: "pipeline",
        message: "No pipeline state file found",
      });
      return c.json(
        {
          ok: true,
          status: "idle",
          message: "No pipeline has been run yet",
        },
        200,
      );
    }

    // Read and parse state file
    const stateContent = readFileSync(statePath, "utf-8");
    const stateData = JSON.parse(stateContent);

    emitStructuredLog({
      severity: "debug",
      source: "api",
      service: "pipeline",
      message: `Pipeline status retrieved for domain ${stateData.domain || "unknown"}`,
    });

    return c.json(
      {
        ok: true,
        status: "active",
        data: stateData,
      },
      200,
    );
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    emitStructuredLog({
      severity: "error",
      source: "api",
      service: "pipeline",
      message: `Failed to retrieve pipeline status: ${errorMsg}`,
    });
    return c.json(
      {
        ok: false,
        status: "error",
        error: "Failed to retrieve pipeline status",
        details: errorMsg,
      },
      500,
    );
  }
});

/**
 * GET /models - List fine-tuned models from registry
 * Returns: { ok: boolean, status: string, data?: object, error?: string }
 */
pipeline.get("/models", async (c: Context) => {
  try {
    // Determine registry file path (relative to api/ directory)
    const registryPath = path.resolve(process.cwd(), "../finetune/promoted_models.local.json");

    // Check if registry file exists
    if (!existsSync(registryPath)) {
      emitStructuredLog({
        severity: "info",
        source: "api",
        service: "pipeline",
        message: "No model registry file found",
      });
      return c.json(
        {
          ok: true,
          status: "empty",
          message: "No models have been registered yet",
          data: { version: 1, models: {} },
        },
        200,
      );
    }

    // Read and parse registry file
    const registryContent = readFileSync(registryPath, "utf-8");
    const registryData = JSON.parse(registryContent);

    emitStructuredLog({
      severity: "debug",
      source: "api",
      service: "pipeline",
      message: `Model registry retrieved with ${Object.keys(registryData.models || {}).length} models`,
    });

    return c.json(
      {
        ok: true,
        status: "success",
        data: registryData,
      },
      200,
    );
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    emitStructuredLog({
      severity: "error",
      source: "api",
      service: "pipeline",
      message: `Failed to retrieve model registry: ${errorMsg}`,
    });
    return c.json(
      {
        ok: false,
        status: "error",
        error: "Failed to retrieve model registry",
        details: errorMsg,
      },
      500,
    );
  }
});

export { pipeline };

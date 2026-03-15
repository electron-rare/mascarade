import { Hono } from "hono";

const version = new Hono();

const CORE_URL = process.env.CORE_URL || "http://localhost:8100";

version.get("/", async (c) => {
  try {
    const res = await fetch(`${CORE_URL}/v1/version`);
    const coreVersion = res.ok ? await res.json() : "unreachable";
    return c.json({
      api_version: "0.1.0",
      service: "mascarade-api",
      core: coreVersion,
      supported_features: [
        "versioned_endpoints",
        "deprecation_headers",
        "openai_compatibility"
      ]
    });
  } catch {
    return c.json({
      api_version: "0.1.0",
      service: "mascarade-api",
      core: "unreachable",
      supported_features: [
        "versioned_endpoints",
        "deprecation_headers",
        "openai_compatibility"
      ]
    }, 503);
  }
});

export { version };

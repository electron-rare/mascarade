import { Hono } from "hono";
import { coreClient, type ProviderStatus } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const llmProviders = new Hono();

function routeConfig() {
  return {
    cheapProvider: (process.env.ROUTELLM_CHEAP_PROVIDER || "ollama").trim() || "ollama",
    cheapModel: (process.env.ROUTELLM_CHEAP_MODEL || "qwen3.5:9b").trim() || "qwen3.5:9b",
    strongProvider: (process.env.ROUTELLM_STRONG_PROVIDER || "claude").trim() || "claude",
    strongModel:
      (process.env.ROUTELLM_STRONG_MODEL || "claude-sonnet-4-6").trim() ||
      "claude-sonnet-4-6",
  };
}

function providerLaneStatus(providerName: string, providers: ProviderStatus[]) {
  const provider = providers.find((entry) => entry.name === providerName);
  if (!provider) {
    return "unavailable";
  }
  if (provider.active) {
    return "active";
  }
  if (provider.configured) {
    return "configured";
  }
  return "inactive";
}

llmProviders.get("/", async (c) => {
  try {
    const [health, providerStatus] = await Promise.all([
      coreClient.health(),
      coreClient.providersStatus(),
    ]);
    const config = routeConfig();
    const providers = providerStatus.providers;

    return c.json({
      ok: true,
      data: {
        healthy: health.status === "ok",
        providers: [
          {
            lane: "cheap",
            provider: config.cheapProvider,
            model: config.cheapModel,
            status: providerLaneStatus(config.cheapProvider, providers),
          },
          {
            lane: "strong",
            provider: config.strongProvider,
            model: config.strongModel,
            status: providerLaneStatus(config.strongProvider, providers),
          },
        ],
        available_providers: providers.map((provider) => ({
          name: provider.name,
          label: provider.label,
          active: provider.active,
          configured: provider.configured,
          default_model: provider.default_model,
          models: provider.models,
        })),
        total: providers.length,
      },
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { llmProviders };

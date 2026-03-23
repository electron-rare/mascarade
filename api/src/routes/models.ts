import { Hono } from "hono";
import { type ProviderStatus, coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const models = new Hono();

type OpenAIModelObject = {
  id: string;
  object: "model";
  created: number;
  owned_by: string;
  provider: string;
  providers: string[];
  active: boolean;
  configured: boolean;
  default: boolean;
};

type MutableOpenAIModelObject = OpenAIModelObject & { _score: number };

const AUTO_ROUTE_MODELS = [
  { id: "auto", routing_policy: "auto", default: true },
  { id: "auto:strong", routing_policy: "strong", default: false },
  { id: "auto:cheap", routing_policy: "cheap", default: false },
  { id: "auto:fast", routing_policy: "fast", default: false },
] as const;

function providerScore(provider: ProviderStatus) {
  if (provider.active) return 2;
  if (provider.configured) return 1;
  return 0;
}

function providerModels(provider: ProviderStatus) {
  return Array.from(
    new Set(
      [provider.default_model, ...provider.models]
        .filter((model): model is string => typeof model === "string" && model.trim().length > 0)
        .map((model) => model.trim()),
    ),
  );
}

function buildModelCatalog(providers: ProviderStatus[]): OpenAIModelObject[] {
  const catalog = new Map<string, MutableOpenAIModelObject>();
  const orderedProviders = [...providers].sort((a, b) => {
    return providerScore(b) - providerScore(a) || a.name.localeCompare(b.name);
  });
  const availableProviderNames = orderedProviders.map((provider) => provider.name);

  for (const provider of orderedProviders) {
    const score = providerScore(provider);
    const defaultModel = provider.default_model?.trim();
    for (const model of providerModels(provider)) {
      const existing = catalog.get(model);
      if (!existing) {
        catalog.set(model, {
          id: model,
          object: "model",
          created: 0,
          owned_by: provider.name,
          provider: provider.name,
          providers: [provider.name],
          active: provider.active,
          configured: provider.configured,
          default: model === defaultModel,
          _score: score,
        });
        continue;
      }

      if (!existing.providers.includes(provider.name)) {
        existing.providers.push(provider.name);
      }
      existing.active = existing.active || provider.active;
      existing.configured = existing.configured || provider.configured;
      existing.default = existing.default || model === defaultModel;
      if (score > existing._score) {
        existing._score = score;
        existing.owned_by = provider.name;
        existing.provider = provider.name;
      }
    }
  }

  const resolvedModels = [...catalog.values()]
    .sort((a, b) => {
      return Number(b.default) - Number(a.default) ||
        Number(b.active) - Number(a.active) ||
        a.id.localeCompare(b.id);
    })
    .map(({ _score: _ignored, ...model }) => model);

  const hasActiveProvider = orderedProviders.some((provider) => provider.active);
  const hasConfiguredProvider = orderedProviders.some((provider) => provider.configured);

  return [
    ...AUTO_ROUTE_MODELS.map((autoModel) => ({
      id: autoModel.id,
      object: "model" as const,
      created: 0,
      owned_by: "mascarade",
      provider: "mascarade",
      providers: availableProviderNames,
      active: hasActiveProvider,
      configured: hasConfiguredProvider,
      default: autoModel.default,
    })),
    ...resolvedModels,
  ];
}

models.get("/", async (c) => {
  try {
    const status = await coreClient.providersStatus();
    return c.json({
      object: "list",
      data: buildModelCatalog(status.providers),
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { models };

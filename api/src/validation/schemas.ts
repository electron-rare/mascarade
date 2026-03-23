import { z } from "zod";

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

export const MessageSchema = z.object({
  role: z.enum(["system", "user", "assistant", "tool"]),
  content: z.string().min(1).max(100_000),
});

export type Message = z.infer<typeof MessageSchema>;

const KnowledgeScopeSchema = z.enum(["project", "federated"]).default("project");
const FederationScopeSchema = z.array(z.string().min(1).max(256)).max(32).optional();
const DEFAULT_PROJECT_ID = (process.env.MASCARADE_PROJECT_ID || "default").trim() || "default";

function withProjectScope<T extends z.ZodRawShape>(shape: T, options?: { defaultProjectId?: string }) {
  return z.object({
    ...shape,
    project_id: options?.defaultProjectId
      ? z.string().min(1).max(256).default(options.defaultProjectId)
      : z.string().min(1).max(256),
    knowledge_scope: KnowledgeScopeSchema,
    federation_scope: FederationScopeSchema,
  }).superRefine((value, ctx) => {
    if (value.knowledge_scope === "federated" && (!value.federation_scope || value.federation_scope.length === 0)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["federation_scope"],
        message: "federation_scope is required when knowledge_scope is federated",
      });
    }
  });
}

// ---------------------------------------------------------------------------
// POST /api/v1/chat/completions
// ---------------------------------------------------------------------------

export const ChatCompletionRequestSchema = withProjectScope(
  {
    model: z.string().max(100).optional(),
    messages: z.array(MessageSchema).min(1).max(200),
    strategy: z.enum(["best", "cheapest", "domain", "fastest", "specific", "routellm"]).optional(),
    routing_policy: z.enum(["auto", "strong", "cheap", "fast"]).optional(),
    temperature: z.number().min(0).max(2).default(0.7),
    max_tokens: z.number().int().min(1).max(128_000).default(4096),
    stream: z.boolean().default(false),
  },
  { defaultProjectId: DEFAULT_PROJECT_ID },
);

export type ChatCompletionRequest = z.infer<typeof ChatCompletionRequestSchema>;

// ---------------------------------------------------------------------------
// Ollama-compatible shims
// ---------------------------------------------------------------------------

const OllamaOptionsSchema = z.object({
  temperature: z.number().min(0).max(2).optional(),
  num_predict: z.number().int().min(1).max(128_000).optional(),
}).passthrough();

export const OllamaChatRequestSchema = withProjectScope(
  {
    model: z.string().max(100).optional(),
    messages: z.array(MessageSchema).min(1).max(200),
    stream: z.boolean().default(true),
    format: z.union([z.literal("json"), z.record(z.string(), z.unknown())]).optional(),
    options: OllamaOptionsSchema.optional(),
    strategy: z.enum(["best", "cheapest", "domain", "fastest", "specific", "routellm"]).optional(),
    routing_policy: z.enum(["auto", "strong", "cheap", "fast"]).optional(),
  },
  { defaultProjectId: DEFAULT_PROJECT_ID },
);

export type OllamaChatRequest = z.infer<typeof OllamaChatRequestSchema>;

export const OllamaGenerateRequestSchema = withProjectScope(
  {
    model: z.string().max(100).optional(),
    prompt: z.string().min(1).max(100_000),
    system: z.string().max(10_000).optional(),
    stream: z.boolean().default(true),
    format: z.union([z.literal("json"), z.record(z.string(), z.unknown())]).optional(),
    options: OllamaOptionsSchema.optional(),
    strategy: z.enum(["best", "cheapest", "domain", "fastest", "specific", "routellm"]).optional(),
    routing_policy: z.enum(["auto", "strong", "cheap", "fast"]).optional(),
  },
  { defaultProjectId: DEFAULT_PROJECT_ID },
);

export type OllamaGenerateRequest = z.infer<typeof OllamaGenerateRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/v1/agents  (create)
// ---------------------------------------------------------------------------

export const AgentCreateRequestSchema = z.object({
  name: z.string().min(1).max(128).regex(/^[\w.-]+$/, "Name must match [\\w.-]+"),
  description: z.string().max(2000),
  system_prompt: z.string().min(1).max(50_000),
  preferred_provider: z.string().max(100).optional(),
  preferred_model: z.string().max(100).optional(),
  preferred_role: z.string().max(100).optional(),
  strategy: z.string().max(50).optional(),
  routing_policy: z.string().max(50).optional(),
  temperature: z.number().min(0).max(2).optional(),
  max_tokens: z.number().int().min(1).max(128_000).optional(),
});

export type AgentCreateRequest = z.infer<typeof AgentCreateRequestSchema>;

// ---------------------------------------------------------------------------
// PUT /api/v1/agents/:name  (update — same shape, name comes from URL)
// ---------------------------------------------------------------------------

export const AgentUpdateRequestSchema = AgentCreateRequestSchema.omit({ name: true }).partial();

export type AgentUpdateRequest = z.infer<typeof AgentUpdateRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/v1/agents/send
// ---------------------------------------------------------------------------

export const SendRequestSchema = withProjectScope({
  messages: z.array(MessageSchema).min(1).max(200),
  strategy: z.string().max(50).optional(),
  routing_policy: z.string().max(50).optional(),
  provider: z.string().max(100).optional(),
  model: z.string().max(100).optional(),
  system: z.string().max(50_000).optional(),
  temperature: z.number().min(0).max(2).optional(),
  max_tokens: z.number().int().min(1).max(128_000).optional(),
});

export type SendRequest = z.infer<typeof SendRequestSchema>;

// ---------------------------------------------------------------------------
// GET /api/v1/knowledge-base/search  (query params, but schema still useful)
// ---------------------------------------------------------------------------

export const KnowledgeBaseSearchSchema = z.object({
  q: z.string().min(1).max(1000),
  limit: z.coerce.number().int().min(1).max(200).optional(),
  project_id: z.string().min(1).max(256),
  knowledge_scope: KnowledgeScopeSchema,
  federation_scope: z.string().max(1000).optional(),
}).superRefine((value, ctx) => {
  if (value.knowledge_scope === "federated" && !value.federation_scope?.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["federation_scope"],
      message: "federation_scope is required when knowledge_scope is federated",
    });
  }
});

export type KnowledgeBaseSearch = z.infer<typeof KnowledgeBaseSearchSchema>;

// ---------------------------------------------------------------------------
// POST /api/v1/agents/:name/run
// ---------------------------------------------------------------------------

export const AgentRunRequestSchema = withProjectScope({
  messages: z.array(MessageSchema).min(1).max(200),
});

export type AgentRunRequest = z.infer<typeof AgentRunRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/cli-agents/run
// ---------------------------------------------------------------------------

export const CliAgentNameSchema = z.enum(["vibe", "codex", "claude-code"]);

export type CliAgentName = z.infer<typeof CliAgentNameSchema>;

export const CliAgentRunRequestSchema = z.object({
  prompt: z.string().min(1).max(100_000),
  workdir: z.string().max(500).optional(),
  agent: CliAgentNameSchema.default("claude-code"),
  max_turns: z.number().int().min(1).max(100).default(20),
  max_price: z.number().min(0).max(50).default(2),
  model: z.string().max(50).default("sonnet"),
  allowed_tools: z.array(z.string().min(1).max(100)).max(64).optional(),
  full_auto: z.boolean().default(true),
});

export type CliAgentRunRequest = z.infer<typeof CliAgentRunRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/providers/codestral/fim
// ---------------------------------------------------------------------------

export const CodestralFIMRequestSchema = z.object({
  prompt: z.string().min(1).max(200_000),
  suffix: z.string().max(200_000).default(""),
  model: z.string().max(100).optional(),
  temperature: z.number().min(0).max(2).default(0),
  max_tokens: z.number().int().min(1).max(32_768).default(1024),
  stop: z.array(z.string().min(1).max(200)).max(16).optional(),
});

export type CodestralFIMRequest = z.infer<typeof CodestralFIMRequestSchema>;

export const KnowledgeScribeRunAndPushRequestSchema = withProjectScope({
  messages: z.array(MessageSchema).min(1).max(200),
  push_to: z.string().max(512).optional(),
  run_id: z.string().max(256).optional(),
});

export type KnowledgeScribeRunAndPushRequest = z.infer<typeof KnowledgeScribeRunAndPushRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/v1/pipeline/run
// ---------------------------------------------------------------------------

export const PipelineRunRequestSchema = z.object({
  domain: z.string().min(1).max(50),
  dry_run: z.boolean().default(false),
});

export type PipelineRunRequest = z.infer<typeof PipelineRunRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/v1/users  (create)
// ---------------------------------------------------------------------------

export const UserCreateRequestSchema = z.object({
  username: z.string().min(1).max(128),
  email: z.string().email().max(256),
  role_id: z.number().int().min(1).max(10).optional(),
  password: z.string().min(8).max(256).optional(),
});

export type UserCreateRequest = z.infer<typeof UserCreateRequestSchema>;

// ---------------------------------------------------------------------------
// PUT /api/v1/users/:userId  (update)
// ---------------------------------------------------------------------------

export const UserUpdateRequestSchema = UserCreateRequestSchema.partial();

export type UserUpdateRequest = z.infer<typeof UserUpdateRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/v1/users/:userId/api-keys
// ---------------------------------------------------------------------------

export const ApiKeyCreateRequestSchema = z.object({
  name: z.string().min(1).max(128).optional(),
  expires_in_days: z.number().int().min(1).max(365).optional(),
});

export type ApiKeyCreateRequest = z.infer<typeof ApiKeyCreateRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/killlife/workflows/:id/run
// ---------------------------------------------------------------------------

export const WorkflowRunRequestSchema = z.object({
  mode: z.enum(["local", "github"]),
  dry_run: z.boolean().default(false),
  inputs: z.record(z.string(), z.unknown()).optional(),
});

export type WorkflowRunRequest = z.infer<typeof WorkflowRunRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/v1/finetune/pipeline
// ---------------------------------------------------------------------------

export const FinetuneRunRequestSchema = z.object({
  task: z.string().min(1).max(256),
  domain: z.string().min(1).max(128).optional(),
  max_model_size_gb: z.coerce.number().positive().finite().optional(),
});

export type FinetuneRunRequest = z.infer<typeof FinetuneRunRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/cluster/forward/send
// ---------------------------------------------------------------------------

export const ClusterForwardSendRequestSchema = z.object({
  messages: z.array(MessageSchema).min(1).max(200),
  target_node: z.string().max(256).optional(),
  strategy: z.string().max(50).optional(),
  model: z.string().max(100).optional(),
  provider: z.string().max(100).optional(),
});

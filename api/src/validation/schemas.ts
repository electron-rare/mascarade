import { z } from "zod";

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

const MAX_MESSAGE_CONTENT_LENGTH = 50_000;
const MAX_MESSAGE_COUNT = 100;
const MAX_COMPLETION_TOKENS = 32_768;
const MAX_PROMPT_LENGTH = 50_000;
const MAX_SYSTEM_PROMPT_LENGTH = 20_000;
const MAX_CODESSTRAL_CONTEXT_LENGTH = 100_000;
const StringListSchema = z.array(z.string().min(1).max(256)).max(128);
const JsonObjectSchema = z.record(z.string(), z.unknown());

const AgentGateRequestSchema = z.object({
  name: z.string().min(1).max(200),
  description: z.string().max(1000).default(""),
  phase: z.enum(["pre", "post"]).default("pre"),
  required: z.boolean().default(true),
  check: z.string().max(200).default(""),
  status: z.enum(["pending", "passed", "failed", "skipped"]).default("pending"),
});

const AgentRoutingOverrideSchema = z.object({
  peer_id: z.string().min(1).max(100).optional(),
  preferred_role: z.string().min(1).max(100).optional(),
  preferred_provider: z.string().min(1).max(100).optional(),
  preferred_model: z.string().min(1).max(100).optional(),
  routing_policy: z.enum(["auto", "strong", "cheap", "fast"]).optional(),
});

export const MessageSchema = z.object({
  role: z.enum(["system", "user", "assistant", "tool"]),
  content: z.string().min(1).max(MAX_MESSAGE_CONTENT_LENGTH),
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
    messages: z.array(MessageSchema).min(1).max(MAX_MESSAGE_COUNT),
    strategy: z.enum(["best", "cheapest", "domain", "fastest", "specific", "routellm"]).optional(),
    routing_policy: z.enum(["auto", "strong", "cheap", "fast"]).optional(),
    temperature: z.number().min(0).max(2).default(0.7),
    max_tokens: z.number().int().min(1).max(MAX_COMPLETION_TOKENS).default(4096),
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
  num_predict: z.number().int().min(1).max(MAX_COMPLETION_TOKENS).optional(),
}).passthrough();

export const OllamaChatRequestSchema = withProjectScope(
  {
    model: z.string().max(100).optional(),
    messages: z.array(MessageSchema).min(1).max(MAX_MESSAGE_COUNT),
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
    prompt: z.string().min(1).max(MAX_PROMPT_LENGTH),
    system: z.string().max(MAX_SYSTEM_PROMPT_LENGTH).optional(),
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
  system_prompt: z.string().min(1).max(MAX_SYSTEM_PROMPT_LENGTH),
  preferred_provider: z.string().max(100).optional(),
  preferred_model: z.string().max(100).optional(),
  preferred_role: z.string().max(100).optional(),
  strategy: z.string().max(50).optional(),
  routing_policy: z.string().max(50).optional(),
  temperature: z.number().min(0).max(2).optional(),
  max_tokens: z.number().int().min(1).max(MAX_COMPLETION_TOKENS).optional(),
  tools: StringListSchema.optional(),
  skills: StringListSchema.optional(),
  category: z.string().max(100).nullable().optional(),
  retry_config: JsonObjectSchema.nullable().optional(),
  gates: z.array(AgentGateRequestSchema).max(64).optional(),
  evidence_refs: StringListSchema.optional(),
  capabilities: StringListSchema.optional(),
  cluster: z.string().max(100).nullable().optional(),
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
  messages: z.array(MessageSchema).min(1).max(MAX_MESSAGE_COUNT),
  strategy: z.string().max(50).optional(),
  routing_policy: z.string().max(50).optional(),
  provider: z.string().max(100).optional(),
  model: z.string().max(100).optional(),
  system: z.string().max(MAX_SYSTEM_PROMPT_LENGTH).optional(),
  temperature: z.number().min(0).max(2).optional(),
  max_tokens: z.number().int().min(1).max(MAX_COMPLETION_TOKENS).optional(),
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
  messages: z.array(MessageSchema).min(1).max(MAX_MESSAGE_COUNT),
});

export type AgentRunRequest = z.infer<typeof AgentRunRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/cli-agents/run
// ---------------------------------------------------------------------------

export const CliAgentNameSchema = z.enum(["vibe", "codex", "claude-code"]);

export type CliAgentName = z.infer<typeof CliAgentNameSchema>;

export const CliAgentRunRequestSchema = z.object({
  prompt: z.string().min(1).max(MAX_PROMPT_LENGTH),
  workdir: z.string().max(500).optional(),
  agent: CliAgentNameSchema.default("claude-code"),
  max_turns: z.number().int().min(1).max(40).default(20),
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
  prompt: z.string().min(1).max(MAX_CODESSTRAL_CONTEXT_LENGTH),
  suffix: z.string().max(MAX_CODESSTRAL_CONTEXT_LENGTH).default(""),
  model: z.string().max(100).optional(),
  temperature: z.number().min(0).max(2).default(0),
  max_tokens: z.number().int().min(1).max(32_768).default(1024),
  stop: z.array(z.string().min(1).max(200)).max(16).optional(),
});

export type CodestralFIMRequest = z.infer<typeof CodestralFIMRequestSchema>;

export const KnowledgeScribeRunAndPushRequestSchema = withProjectScope({
  messages: z.array(MessageSchema).min(1).max(MAX_MESSAGE_COUNT),
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
  messages: z.array(MessageSchema).min(1).max(MAX_MESSAGE_COUNT),
  peer_id: z.string().max(256).optional(),
  preferred_role: z.string().max(100).optional(),
  allow_local: z.boolean().optional(),
  target_node: z.string().max(256).optional(),
  strategy: z.string().max(50).optional(),
  model: z.string().max(100).optional(),
  provider: z.string().max(100).optional(),
  routing_policy: z.string().max(50).optional(),
  system: z.string().max(MAX_SYSTEM_PROMPT_LENGTH).nullable().optional(),
  temperature: z.number().min(0).max(2).optional(),
  max_tokens: z.number().int().min(1).max(MAX_COMPLETION_TOKENS).optional(),
  project_id: z.string().min(1).max(256).optional(),
  knowledge_scope: z.enum(["project", "federated"]).optional(),
  federation_scope: z.array(z.string().min(1).max(256)).max(32).optional(),
});

export type ClusterForwardSendRequest = z.infer<typeof ClusterForwardSendRequestSchema>;

// ---------------------------------------------------------------------------
<<<<<<< Updated upstream
// /api/orchestrate/templates
// ---------------------------------------------------------------------------

export const WorkflowTemplateCreateRequestSchema = z.object({
  id: z.string().min(1).max(100).regex(/^[\w.-]+$/, "Template id must match [\\w.-]+"),
  name: z.string().min(1).max(200),
  description: z.string().max(1000).default(""),
  agent_names: z.array(z.string().min(1).max(128)).min(1).max(20),
  mode: z.enum(["sequential", "parallel", "pipeline"]).default("sequential"),
  routing_overrides: z.record(z.string(), AgentRoutingOverrideSchema).optional(),
  documentation: z.string().max(5000).default(""),
});

export type WorkflowTemplateCreateRequest = z.infer<typeof WorkflowTemplateCreateRequestSchema>;

export const WorkflowTemplateUpdateRequestSchema = WorkflowTemplateCreateRequestSchema.omit({
  id: true,
}).partial();

export type WorkflowTemplateUpdateRequest = z.infer<typeof WorkflowTemplateUpdateRequestSchema>;

export const TemplateDeployRequestSchema = z.object({
  input: z.string().min(1).max(MAX_PROMPT_LENGTH),
  routing_overrides: z.record(z.string(), AgentRoutingOverrideSchema).optional(),
});

export type TemplateDeployRequest = z.infer<typeof TemplateDeployRequestSchema>;
=======
// Wizard Agents Management Schemas
// ---------------------------------------------------------------------------

const MAX_TASK_LENGTH = 2000;
const MAX_DOMAIN_LENGTH = 50;
const MAX_AGENT_NAME_LENGTH = 128;
const MAX_ERROR_LENGTH = 1000;

export const ExecutionModeSchema = z.enum(["sequential", "parallel"]);
export type ExecutionMode = z.infer<typeof ExecutionModeSchema>;

export const WizardRunStatusSchema = z.enum([
  "pending",
  "selecting",
  "running",
  "completed",
  "failed",
  "timeout",
]);
export type WizardRunStatus = z.infer<typeof WizardRunStatusSchema>;

export const AgentSelectionStatusSchema = z.enum([
  "pending",
  "running",
  "completed",
  "failed",
  "timeout",
]);
export type AgentSelectionStatus = z.infer<typeof AgentSelectionStatusSchema>;

export const CostClassSchema = z.enum(["low", "medium", "high"]);
export type CostClass = z.infer<typeof CostClassSchema>;

// Constraints
export const ExecutionConstraintsSchema = z.object({
  max_cost: z.number().min(0).max(100).default(1.0),
  max_latency_ms: z.number().int().min(100).max(120_000).default(10_000),
  required_models: z.array(z.string().min(1).max(128)).max(10).default([]),
}).superRefine((value, ctx) => {
  if (value.required_models.length > 0 && !value.required_models.every((m) => m.trim())) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["required_models"],
      message: "Each model name must be non-empty",
    });
  }
});

export type ExecutionConstraints = z.infer<typeof ExecutionConstraintsSchema>;

// Metrics
export const ExecutionMetricsSchema = z.object({
  duration_ms: z.number().min(0),
  tokens_used: z.number().int().min(0).default(0),
  cost_usd: z.number().min(0),
  provider_used: z.string().max(128).nullable().optional(),
});

export type ExecutionMetrics = z.infer<typeof ExecutionMetricsSchema>;

// POST /api/wizard/run — Request
export const WizardAgentRunRequestSchema = withProjectScope(
  {
    task: z.string().min(5).max(MAX_TASK_LENGTH),
    domain: z
      .string()
      .min(1)
      .max(MAX_DOMAIN_LENGTH)
      .regex(/^[a-z_]+$/, "domain must be lowercase letters and underscores"),
    constraints: ExecutionConstraintsSchema.optional(),
    context: z.record(z.string(), z.unknown()).default({}),
    execution_mode: ExecutionModeSchema.default("sequential"),
    timeout_seconds: z.number().min(10).max(3600).default(120),
    continue_on_error: z.boolean().default(false),
    fail_on_partial: z.boolean().default(true),
  },
  { defaultProjectId: DEFAULT_PROJECT_ID },
).superRefine((value, ctx) => {
  const validDomains = [
    "electronics",
    "rag",
    "orchestration",
    "code",
    "design",
    "analysis",
    "generation",
    "validation",
  ];
  if (!validDomains.includes(value.domain)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["domain"],
      message: `domain must be one of: ${validDomains.join(", ")}`,
    });
  }
});

export type WizardAgentRunRequest = z.infer<typeof WizardAgentRunRequestSchema>;

// Selected Agent Info
export const SelectedAgentInfoSchema = z.object({
  name: z.string().min(1).max(MAX_AGENT_NAME_LENGTH),
  domain: z.string().min(1).max(MAX_DOMAIN_LENGTH),
  selection_score: z.number().min(0).max(1),
  cost_class: CostClassSchema,
});

export type SelectedAgentInfo = z.infer<typeof SelectedAgentInfoSchema>;

// Selection Result
export const WizardAgentSelectionResultSchema = z.object({
  task_id: z.string().min(1).max(256),
  selected_agents: z.array(SelectedAgentInfoSchema).default([]),
  total_agents_evaluated: z.number().int().min(0),
  selection_timestamp: z.date().default(() => new Date()),
});

export type WizardAgentSelectionResult = z.infer<typeof WizardAgentSelectionResultSchema>;

// Agent Result
export const WizardAgentResultSchema = z
  .object({
    task_id: z.string().min(1).max(256),
    agent_name: z.string().min(1).max(MAX_AGENT_NAME_LENGTH),
    status: AgentSelectionStatusSchema,
    output: z.record(z.string(), z.unknown()).nullable().optional(),
    error: z.string().max(MAX_ERROR_LENGTH).nullable().optional(),
    metrics: ExecutionMetricsSchema.optional(),
    completion_timestamp: z.date().default(() => new Date()),
  })
  .superRefine((value, ctx) => {
    if (value.status === "completed" && !value.output) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["output"],
        message: "output is required when status is completed",
      });
    }
    if (value.status === "failed" && !value.error) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["error"],
        message: "error is required when status is failed",
      });
    }
  });

export type WizardAgentResult = z.infer<typeof WizardAgentResultSchema>;

// Aggregated Analysis
export const AggregatedAnalysisSchema = z.object({
  summary: z.string().max(2000).default(""),
  confidence: z.number().min(0).max(1).default(0.5),
  raw_analyses: z.record(z.string(), z.unknown()).default({}),
});

export type AggregatedAnalysis = z.infer<typeof AggregatedAnalysisSchema>;

// Final Run Result
export const WizardRunResultSchema = z.object({
  task_id: z.string().min(1).max(256),
  status: WizardRunStatusSchema,
  execution_mode: ExecutionModeSchema,
  results: z.array(WizardAgentResultSchema).default([]),
  aggregated_analysis: AggregatedAnalysisSchema.optional(),
  total_duration_ms: z.number().min(0).default(0),
  total_cost_usd: z.number().min(0).default(0),
  completion_timestamp: z.date().default(() => new Date()),
  error_reason: z.string().max(MAX_ERROR_LENGTH).nullable().optional(),
});

export type WizardRunResult = z.infer<typeof WizardRunResultSchema>;

// Status Response
export const WizardRunStatusResponseSchema = z.object({
  task_id: z.string().min(1).max(256),
  status: WizardRunStatusSchema,
  progress_percent: z.number().int().min(0).max(100),
  results: z.array(WizardAgentResultSchema).optional(),
  error: z.string().max(MAX_ERROR_LENGTH).nullable().optional(),
  last_update: z.date().default(() => new Date()),
});

export type WizardRunStatusResponse = z.infer<typeof WizardRunStatusResponseSchema>;

// Agent Capability
export const AgentCapabilitySchema = z.object({
  name: z.string().min(1).max(MAX_AGENT_NAME_LENGTH),
  domain: z.string().min(1).max(MAX_DOMAIN_LENGTH),
  required_context: z.array(z.string().min(1).max(256)).default([]),
  cost_class: CostClassSchema,
  concurrent_limit: z.number().int().min(1).default(1),
  timeout_seconds: z.number().min(10).max(3600).default(300),
  circuit_breaker_enabled: z.boolean().default(true),
});

export type AgentCapability = z.infer<typeof AgentCapabilitySchema>;

// Capability Matrix
export const WizardAgentCapabilityMatrixSchema = z.object({
  timestamp: z.date().default(() => new Date()),
  agents: z.record(z.string().min(1).max(MAX_AGENT_NAME_LENGTH), AgentCapabilitySchema).default({}),
  domain_to_agents: z.record(z.string().min(1).max(MAX_DOMAIN_LENGTH), z.array(z.string())).default({}),
  total_agents: z.number().int().min(0),
});

export type WizardAgentCapabilityMatrix = z.infer<typeof WizardAgentCapabilityMatrixSchema>;
>>>>>>> Stashed changes

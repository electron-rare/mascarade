import { z } from "zod";

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

export const MessageSchema = z.object({
  role: z.enum(["system", "user", "assistant", "tool"]),
  content: z.string().min(1).max(100_000),
});

export type Message = z.infer<typeof MessageSchema>;

// ---------------------------------------------------------------------------
// POST /api/v1/chat/completions
// ---------------------------------------------------------------------------

export const ChatCompletionRequestSchema = z.object({
  model: z.string().max(100).optional(),
  messages: z.array(MessageSchema).min(1).max(200),
  temperature: z.number().min(0).max(2).default(0.7),
  max_tokens: z.number().int().min(1).max(128_000).default(4096),
  stream: z.boolean().default(false),
});

export type ChatCompletionRequest = z.infer<typeof ChatCompletionRequestSchema>;

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

export const SendRequestSchema = z.object({
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
  limit: z.number().int().min(1).max(200).optional(),
  project_id: z.string().max(256).optional(),
  knowledge_scope: z.string().max(256).optional(),
  federation_scope: z.string().max(1000).optional(),
});

export type KnowledgeBaseSearch = z.infer<typeof KnowledgeBaseSearchSchema>;

// ---------------------------------------------------------------------------
// POST /api/v1/agents/:name/run
// ---------------------------------------------------------------------------

export const AgentRunRequestSchema = z.object({
  messages: z.array(MessageSchema).min(1).max(200),
});

export type AgentRunRequest = z.infer<typeof AgentRunRequestSchema>;

// ---------------------------------------------------------------------------
// POST /api/v1/pipeline/run
// ---------------------------------------------------------------------------

export const PipelineRunRequestSchema = z.object({
  domain: z.string().min(1).max(50),
  dry_run: z.boolean().default(false),
});

export type PipelineRunRequest = z.infer<typeof PipelineRunRequestSchema>;

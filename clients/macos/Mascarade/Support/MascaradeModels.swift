//
//  MascaradeModels.swift
//  Mascarade
//
//  Created by Codex on 07/03/2026.
//

import Foundation

nonisolated struct HealthResponse: Decodable {
    let status: String
    let core: CoreHealth?
}

nonisolated struct CoreHealth: Decodable {
    let status: String
}

nonisolated struct OpsSummary: Decodable {
    let timestamp: String
    let monitor: MonitorSnapshot
    let traces: TraceSummary
    let alerts: [AlertEntry]
    let cluster: ClusterSnapshot?
}

nonisolated struct MonitorSnapshot: Decodable {
    let gateway: GatewaySnapshot
    let ai: AISnapshot
    let services: [ServiceSnapshot]
}

nonisolated struct GatewaySnapshot: Decodable {
    let api: GatewayAPI
    let core: Bool
}

nonisolated struct GatewayAPI: Decodable {
    let ok: Bool
    let status: Int
}

nonisolated struct AISnapshot: Decodable {
    let ollama: ProviderSnapshot
    let qdrant: ProviderSnapshot
}

nonisolated struct ProviderSnapshot: Decodable {
    let ok: Bool
    let status: Int
    let latencyMs: Double?
    let models: Int?
    let collections: Int?
}

nonisolated struct ServiceSnapshot: Decodable, Identifiable {
    let name: String
    let url: String
    let ok: Bool
    let status: Int
    let latencyMs: Double?

    var id: String { name }
}

nonisolated struct TraceSummary: Decodable {
    let totalRecent: Int
    let activeRuns: Int
    let recentRuns: [RecentRun]
}

nonisolated struct RecentRun: Decodable, Identifiable {
    let runId: String
    let mode: String
    let agentName: String?
    let eventType: String
    let ts: String
    let message: String

    var id: String { "\(runId)-\(ts)-\(eventType)" }
}

nonisolated struct AlertEntry: Decodable, Identifiable {
    let id: String
    let ts: String
    let source: String
    let service: String?
    let severity: String
    let message: String
}

nonisolated struct ClusterSnapshot: Decodable {
    let enabled: Bool
    let nodeId: String?
    let role: String?
    let peersTotal: Int
    let peersOk: Int
}

nonisolated struct AgentsPayload: Decodable {
    let agents: [AgentSummary]
}

nonisolated struct AgentSummary: Decodable, Identifiable {
    let name: String
    let description: String
    let preferredProvider: String?
    let preferredModel: String?
    let preferredRole: String?
    let strategy: String?
    let builtin: Bool

    var id: String { name }
}

nonisolated struct WorkflowsPayload: Decodable {
    let workflows: [WorkflowSummary]
}

nonisolated struct WorkflowSummary: Decodable, Identifiable {
    let id: String
    let title: String
    let category: String
    let status: String
    let version: Int
    let tags: [String]
    let executionModes: [String]
    let nodeCount: Int
    let edgeCount: Int
    let updatedAt: String
    let latestRun: LatestRunSummary?
}

nonisolated struct LatestRunSummary: Decodable {
    let runId: String
    let mode: String
    let status: String
    let finishedAt: String
}

// MARK: - Chat Completions

struct ChatMessage: Codable {
    let role: String
    let content: String
}

struct ChatCompletionRequest: Encodable {
    let model: String
    let messages: [ChatMessage]
    let maxTokens: Int?
    let temperature: Double?
    let stream: Bool
    let projectId: String

    enum CodingKeys: String, CodingKey {
        case model, messages, stream
        case maxTokens = "max_tokens"
        case temperature
        case projectId = "project_id"
    }
}

nonisolated struct ChatCompletionResponse: Decodable {
    let id: String
    let model: String
    let choices: [ChatChoice]
    let usage: ChatUsage?
}

nonisolated struct ChatChoice: Decodable {
    let index: Int
    let message: ChatMessage
    let finishReason: String?
}

nonisolated struct ChatUsage: Decodable {
    let promptTokens: Int
    let completionTokens: Int
    let totalTokens: Int
}

// MARK: - Agent Zero Copilot

struct CopilotRequest: Encodable {
    let mode: String
    let prompt: String
    let logs: [String]
    let traces: [[String: String]]
    let service: String?
    let severity: String?
    let projectId: String?

    enum CodingKeys: String, CodingKey {
        case mode, prompt, logs, traces, service, severity
        case projectId = "project_id"
    }
}

nonisolated struct CopilotResponse: Decodable {
    let content: String
    let model: String
    let provider: String
    let usage: [String: Int]?
    let operatorContext: CopilotContext?
}

nonisolated struct CopilotContext: Decodable {
    let mode: String?
    let service: String?
    let severity: String?
    let runId: String?
    let logsCount: Int?
    let tracesCount: Int?
}

// MARK: - Mistral Batch

struct BatchSubmitRequest: Encodable {
    let model: String
    let endpoint: String
    let metadata: [String: String]

    init(model: String = "mistral-large-latest", metadata: [String: String] = [:]) {
        self.model = model
        self.endpoint = "/v1/chat/completions"
        self.metadata = metadata
    }
}

nonisolated struct BatchJobResponse: Decodable {
    let jobId: String
    let status: String
    let model: String
    let totalRequests: Int
    let succeededRequests: Int?
    let failedRequests: Int?
    let outputFile: String?
    let createdAt: String?
}

nonisolated struct BatchResultsResponse: Decodable {
    let jobId: String
    let model: String
    let status: String
    let results: [BatchResult]
}

nonisolated struct BatchResult: Decodable, Identifiable {
    let customId: String
    let content: String
    let usage: BatchResultUsage?

    var id: String { customId }
}

nonisolated struct BatchResultUsage: Decodable {
    let promptTokens: Int?
    let completionTokens: Int?
}

nonisolated struct BatchPresetsResponse: Decodable, Sendable {
    // Dynamic keys — decode manually if needed
}

import Foundation

// MARK: - OpenAI-compatible request/response types

struct ChatCompletionRequest: Codable, Sendable {
    let model: String?
    let messages: [ChatMessage]
    let temperature: Double?
    let max_tokens: Int?
    let stream: Bool?
}

struct ChatMessage: Codable, Sendable {
    let role: String
    let content: String
}

struct ChatCompletionResponse: Codable, Sendable {
    let id: String
    let object: String
    let created: Int
    let model: String
    let choices: [Choice]
    let usage: Usage

    struct Choice: Codable, Sendable {
        let index: Int
        let message: ChatMessage
        let finish_reason: String
    }

    struct Usage: Codable, Sendable {
        let prompt_tokens: Int
        let completion_tokens: Int
        let total_tokens: Int
    }
}

struct ChatCompletionChunk: Codable, Sendable {
    let id: String
    let object: String
    let created: Int
    let model: String
    let choices: [StreamChoice]

    struct StreamChoice: Codable, Sendable {
        let index: Int
        let delta: Delta
        let finish_reason: String?
    }

    struct Delta: Codable, Sendable {
        let role: String?
        let content: String?
    }
}

struct ModelListResponse: Codable, Sendable {
    let object: String
    let data: [ModelEntry]

    struct ModelEntry: Codable, Sendable {
        let id: String
        let object: String
        let created: Int
        let owned_by: String
    }
}

struct HealthResponse: Codable, Sendable {
    let status: String
    let model: String
}

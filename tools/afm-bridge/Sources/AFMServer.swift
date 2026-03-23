import Foundation
import Hummingbird
import FoundationModels

/// HTTP server bridging Apple Foundation Models to an OpenAI-compatible API.
struct AFMServer {
    let port: Int
    let modelName = "apple-fm-3b"

    func run() async throws {
        let router = Router()
        let session = LanguageModelSession()

        // GET /health
        router.get("/health") { _, _ in
            let response = HealthResponse(status: "ok", model: modelName)
            return try JSONEncoder().encode(response)
        }

        // GET /v1/models
        router.get("/v1/models") { _, _ in
            let response = ModelListResponse(
                object: "list",
                data: [
                    .init(
                        id: modelName,
                        object: "model",
                        created: Int(Date().timeIntervalSince1970),
                        owned_by: "apple"
                    )
                ]
            )
            return try JSONEncoder().encode(response)
        }

        // POST /v1/chat/completions
        router.post("/v1/chat/completions") { request, context in
            let body = try await request.body.collect(upTo: 1_048_576)
            let req = try JSONDecoder().decode(ChatCompletionRequest.self, from: body)

            // Build prompt from messages
            let prompt = req.messages.map { msg in
                switch msg.role {
                case "system": return "System: \(msg.content)"
                case "assistant": return "Assistant: \(msg.content)"
                default: return msg.content
                }
            }.joined(separator: "\n")

            let requestId = "chatcmpl-\(UUID().uuidString.prefix(8))"
            let created = Int(Date().timeIntervalSince1970)
            let model = req.model ?? modelName

            if req.stream == true {
                // SSE streaming response
                return Response(
                    status: .ok,
                    headers: [
                        .contentType: "text/event-stream",
                        .cacheControl: "no-cache",
                        .init("Connection")!: "keep-alive",
                    ],
                    body: .init { writer in
                        // Role chunk
                        let roleChunk = ChatCompletionChunk(
                            id: requestId,
                            object: "chat.completion.chunk",
                            created: created,
                            model: model,
                            choices: [.init(index: 0, delta: .init(role: "assistant", content: nil), finish_reason: nil)]
                        )
                        let roleData = try JSONEncoder().encode(roleChunk)
                        try await writer.write(ByteBuffer(string: "data: \(String(data: roleData, encoding: .utf8)!)\n\n"))

                        // Stream tokens
                        for try await token in session.streamResponse(to: prompt) {
                            let chunk = ChatCompletionChunk(
                                id: requestId,
                                object: "chat.completion.chunk",
                                created: created,
                                model: model,
                                choices: [.init(index: 0, delta: .init(role: nil, content: String(token)), finish_reason: nil)]
                            )
                            let chunkData = try JSONEncoder().encode(chunk)
                            try await writer.write(ByteBuffer(string: "data: \(String(data: chunkData, encoding: .utf8)!)\n\n"))
                        }

                        // Stop chunk
                        let stopChunk = ChatCompletionChunk(
                            id: requestId,
                            object: "chat.completion.chunk",
                            created: created,
                            model: model,
                            choices: [.init(index: 0, delta: .init(role: nil, content: nil), finish_reason: "stop")]
                        )
                        let stopData = try JSONEncoder().encode(stopChunk)
                        try await writer.write(ByteBuffer(string: "data: \(String(data: stopData, encoding: .utf8)!)\n\n"))
                        try await writer.write(ByteBuffer(string: "data: [DONE]\n\n"))

                        try await writer.finish(nil)
                    }
                )
            } else {
                // Non-streaming response
                let response = try await session.respond(to: prompt)
                let content = String(describing: response)

                let promptTokens = prompt.count / 4  // rough estimate
                let completionTokens = content.count / 4

                let chatResponse = ChatCompletionResponse(
                    id: requestId,
                    object: "chat.completion",
                    created: created,
                    model: model,
                    choices: [
                        .init(
                            index: 0,
                            message: ChatMessage(role: "assistant", content: content),
                            finish_reason: "stop"
                        )
                    ],
                    usage: .init(
                        prompt_tokens: promptTokens,
                        completion_tokens: completionTokens,
                        total_tokens: promptTokens + completionTokens
                    )
                )
                let responseData = try JSONEncoder().encode(chatResponse)
                return Response(
                    status: .ok,
                    headers: [.contentType: "application/json"],
                    body: .init(byteBuffer: ByteBuffer(data: responseData))
                )
            }
        }

        let app = Application(
            router: router,
            configuration: .init(address: .hostname("127.0.0.1", port: port))
        )

        print("AFM Bridge listening on http://127.0.0.1:\(port)")
        try await app.run()
    }
}

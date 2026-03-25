//
//  AperantAPI.swift
//  Mascarade
//
//  Client HTTP pour le bridge aperant-bridge.
//  Même pattern que MascaradeAPI — retry exponentiel, bearer token.
//

import Foundation

struct AperantAPI {
    let baseURL: URL
    let apiKey: String
    let session: URLSession

    private static let maxAttempts = 3

    init(baseURL: URL, apiKey: String, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.apiKey = apiKey
        self.session = session
    }

    // MARK: - GET helpers

    func health() async throws -> AperantHealth {
        try await get("/health", as: AperantHealth.self)
    }

    func listSpecs() async throws -> [AperantSpecSummary] {
        try await get("/specs", as: [AperantSpecSummary].self)
    }

    func getSpec(_ id: String) async throws -> AperantSpecDetail {
        try await get("/specs/\(id)", as: AperantSpecDetail.self)
    }

    func getPlan(_ specId: String) async throws -> AperantPlan {
        try await get("/specs/\(specId)/plan", as: AperantPlan.self)
    }

    // MARK: - POST

    func createSpec(_ request: AperantCreateRequest) async throws -> AperantSpecDetail {
        try await post("/specs", body: request, as: AperantSpecDetail.self)
    }

    // MARK: - DELETE

    func deleteSpec(_ id: String) async throws {
        guard let url = URL(string: baseURL.absoluteString + "/specs/\(id)") else {
            throw AperantAPIError("URL invalide pour la suppression du spec \(id).")
        }
        var req = URLRequest(url: url)
        req.httpMethod = "DELETE"
        req.timeoutInterval = 20
        applyHeaders(to: &req)

        let (_, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else {
            throw AperantAPIError("Réponse HTTP invalide.")
        }
        guard http.statusCode == 204 || (200..<300).contains(http.statusCode) else {
            throw AperantAPIError("Suppression échouée: HTTP \(http.statusCode)")
        }
    }

    // MARK: - Generic GET

    private func get<T: Decodable>(_ path: String, as type: T.Type = T.self) async throws -> T {
        guard let url = URL(string: baseURL.absoluteString + path) else {
            throw AperantAPIError("URL invalide pour \(path).")
        }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        req.timeoutInterval = 20
        applyHeaders(to: &req)
        return try await execute(req, as: T.self, path: path)
    }

    // MARK: - Generic POST

    private func post<B: Encodable, T: Decodable>(
        _ path: String,
        body: B,
        as type: T.Type = T.self
    ) async throws -> T {
        guard let url = URL(string: baseURL.absoluteString + path) else {
            throw AperantAPIError("URL invalide pour \(path).")
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = 30
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyHeaders(to: &req)

        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        req.httpBody = try encoder.encode(body)

        return try await execute(req, as: T.self, path: path)
    }

    // MARK: - Execution with retry

    private func execute<T: Decodable>(
        _ request: URLRequest,
        as type: T.Type,
        path: String
    ) async throws -> T {
        var lastError: Error = AperantAPIError("Aucune tentative effectuée.")

        for attempt in 0..<Self.maxAttempts {
            if attempt > 0 {
                let delay = UInt64(attempt) * 1_000_000_000
                try await Task.sleep(nanoseconds: delay)
            }

            do {
                let (data, response) = try await session.data(for: request)
                guard let http = response as? HTTPURLResponse else {
                    throw AperantAPIError("Réponse HTTP invalide.")
                }
                guard (200..<300).contains(http.statusCode) else {
                    let msg = String(data: data, encoding: .utf8)?
                        .trimmingCharacters(in: .whitespacesAndNewlines)
                    let detail = (msg?.isEmpty == false ? msg : nil) ?? "HTTP \(http.statusCode)"
                    let error = AperantAPIError(detail)
                    // Erreurs client (4xx) → pas de retry
                    if (400..<500).contains(http.statusCode) {
                        throw error
                    }
                    lastError = error
                    continue
                }
                do {
                    return try decoder.decode(T.self, from: data)
                } catch {
                    throw AperantAPIError("Décodage JSON impossible pour \(path): \(error.localizedDescription)")
                }
            } catch let error as AperantAPIError {
                throw error
            } catch {
                lastError = error
            }
        }

        throw lastError
    }

    // MARK: - Helpers

    private func applyHeaders(to request: inout URLRequest) {
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if !apiKey.isEmpty {
            request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        }
    }

    private var decoder: JSONDecoder {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }
}

// MARK: - Error

struct AperantAPIError: LocalizedError {
    private let message: String

    init(_ message: String) {
        self.message = message
    }

    var errorDescription: String? { message }
}

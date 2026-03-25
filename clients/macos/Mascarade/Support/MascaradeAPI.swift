//
//  MascaradeAPI.swift
//  Mascarade
//
//  Created by Codex on 07/03/2026.
//

import Foundation

struct MascaradeAPI {
    let baseURL: URL
    let apiKey: String
    let session: URLSession
    /// Multiplicateur du délai de backoff en nanosecondes. Mettre à 0 dans les tests.
    let retryDelayNanoseconds: UInt64

    /// Nombre max de tentatives (1 initial + 2 retries).
    private static let maxAttempts = 3

    init(baseURL: URL, apiKey: String, session: URLSession = .shared, retryDelayNanoseconds: UInt64 = 1_000_000_000) {
        self.baseURL = baseURL
        self.apiKey = apiKey
        self.session = session
        self.retryDelayNanoseconds = retryDelayNanoseconds
    }

    func get<T: Decodable>(_ path: String, as type: T.Type = T.self) async throws -> T {
        guard let url = URL(string: baseURL.absoluteString + path) else {
            throw MascaradeAPIError("Impossible de construire l'URL \(path).")
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        if !apiKey.isEmpty {
            request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        }

        var lastError: Error = MascaradeAPIError("Aucune tentative effectuee.")

        for attempt in 0..<Self.maxAttempts {
            // Backoff exponentiel: 0s, 1×delay, 2×delay
            if attempt > 0 {
                let delay = UInt64(attempt) * retryDelayNanoseconds
                if delay > 0 { try await Task.sleep(nanoseconds: delay) }
            }

            do {
                let (data, response) = try await session.data(for: request)
                guard let httpResponse = response as? HTTPURLResponse else {
                    throw MascaradeAPIError("Reponse HTTP invalide.")
                }

                guard (200..<300).contains(httpResponse.statusCode) else {
                    let serverMessage = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
                    let detail = serverMessage.flatMap { $0.isEmpty ? nil : $0 } ?? "HTTP \(httpResponse.statusCode)"
                    let error = MascaradeAPIError(detail)
                    // Ne pas retenter les erreurs client (4xx) ni 501.
                    if (400..<500).contains(httpResponse.statusCode) || httpResponse.statusCode == 501 {
                        throw error
                    }
                    lastError = error
                    continue
                }

                do {
                    return try decoder.decode(T.self, from: data)
                } catch {
                    throw MascaradeAPIError("Decodage JSON impossible pour \(path): \(error.localizedDescription)")
                }

            } catch let error as MascaradeAPIError {
                throw error // Erreurs non-retryables ou decodage: on propage immediatement.
            } catch {
                // URLError (timeout, connexion refusee, etc.) → on retente.
                lastError = error
            }
        }

        throw lastError
    }

    func post<T: Decodable>(_ path: String, body: some Encodable, as type: T.Type = T.self) async throws -> T {
        guard let url = URL(string: baseURL.absoluteString + path) else {
            throw MascaradeAPIError("Impossible de construire l'URL \(path).")
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        if !apiKey.isEmpty {
            request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        }

        request.httpBody = try JSONEncoder().encode(body)

        var lastError: Error = MascaradeAPIError("Aucune tentative effectuee.")

        for attempt in 0..<Self.maxAttempts {
            if attempt > 0 {
                let delay = UInt64(attempt) * retryDelayNanoseconds
                if delay > 0 { try await Task.sleep(nanoseconds: delay) }
            }

            do {
                let (data, response) = try await session.data(for: request)
                guard let httpResponse = response as? HTTPURLResponse else {
                    throw MascaradeAPIError("Reponse HTTP invalide.")
                }

                guard (200..<300).contains(httpResponse.statusCode) else {
                    let serverMessage = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
                    let detail = serverMessage.flatMap { $0.isEmpty ? nil : $0 } ?? "HTTP \(httpResponse.statusCode)"
                    let error = MascaradeAPIError(detail)
                    if (400..<500).contains(httpResponse.statusCode) || httpResponse.statusCode == 501 {
                        throw error
                    }
                    lastError = error
                    continue
                }

                do {
                    return try decoder.decode(T.self, from: data)
                } catch {
                    throw MascaradeAPIError("Decodage JSON impossible pour \(path): \(error.localizedDescription)")
                }

            } catch let error as MascaradeAPIError {
                throw error
            } catch {
                lastError = error
            }
        }

        throw lastError
    }

    private var decoder: JSONDecoder {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }
}

struct MascaradeAPIError: LocalizedError {
    private let message: String

    init(_ message: String) {
        self.message = message
    }

    var errorDescription: String? {
        message
    }
}

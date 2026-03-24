//
//  MascaradeAPITests.swift
//  MascaradeTests
//
//  Tests for MascaradeAPI HTTP client: decoding, error handling, retry logic.
//

import Foundation
import Testing
@testable import Mascarade

// MARK: - Mock infrastructure

/// URLProtocol subclass that serves pre-configured responses without network.
private final class MockURLProtocol: URLProtocol {
    // Per-test responses, indexed by call order.
    nonisolated(unsafe) static var responses: [(Data, HTTPURLResponse)] = []
    nonisolated(unsafe) static var callCount = 0

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let index = min(MockURLProtocol.callCount, MockURLProtocol.responses.count - 1)
        MockURLProtocol.callCount += 1
        let (data, response) = MockURLProtocol.responses[index]
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

private func makeMockSession() -> URLSession {
    let config = URLSessionConfiguration.ephemeral
    config.protocolClasses = [MockURLProtocol.self]
    return URLSession(configuration: config)
}

/// URLProtocol that captures the outgoing request for header inspection.
private final class HeaderCapturingProtocol: URLProtocol {
    nonisolated(unsafe) static var capturedRequest: URLRequest?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for r: URLRequest) -> URLRequest { r }

    override func startLoading() {
        HeaderCapturingProtocol.capturedRequest = request
        let data = #"{"status":"ok"}"#.data(using: .utf8)!
        let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

private func mockResponse(
    status: Int = 200,
    body: String = "{}",
    url: URL = URL(string: "http://localhost")!
) -> (Data, HTTPURLResponse) {
    let data = body.data(using: .utf8)!
    let response = HTTPURLResponse(url: url, statusCode: status, httpVersion: nil, headerFields: nil)!
    return (data, response)
}

private func makeAPI(responses: [(Data, HTTPURLResponse)]) -> MascaradeAPI {
    MockURLProtocol.responses = responses
    MockURLProtocol.callCount = 0
    return MascaradeAPI(
        baseURL: URL(string: "http://localhost")!,
        apiKey: "",
        session: makeMockSession(),
        retryDelayNanoseconds: 0
    )
}

// MARK: - A minimal decodable type for tests

private struct Pong: Decodable, Equatable {
    let status: String
}

// MARK: - Tests

@Suite(.serialized)
struct MascaradeAPITests {

    // MARK: Happy path

    @Test func decodesSuccessfulResponse() async throws {
        let api = makeAPI(responses: [mockResponse(body: #"{"status":"ok"}"#)])
        let pong: Pong = try await api.get("/ping")
        #expect(pong.status == "ok")
    }

    @Test func decodesSnakeCaseKeys() async throws {
        // HealthResponse uses snake_case -> camelCase (keyDecodingStrategy)
        let json = #"{"status":"ok","core":{"status":"ok"}}"#
        let api = makeAPI(responses: [mockResponse(body: json)])
        let health: HealthResponse = try await api.get("/health")
        #expect(health.status == "ok")
        #expect(health.core?.status == "ok")
    }

    // MARK: Error handling

    @Test func throws400ImmediatelyWithoutRetry() async throws {
        let api = makeAPI(responses: [
            mockResponse(status: 400, body: "Bad Request"),
            mockResponse(body: #"{"status":"ok"}"#), // should never be reached
        ])

        await #expect(throws: (any Error).self) {
            let _: Pong = try await api.get("/ping")
        }
        // Only 1 attempt should have been made (no retry on 4xx).
        #expect(MockURLProtocol.callCount == 1)
    }

    @Test func throws401ImmediatelyWithoutRetry() async throws {
        let api = makeAPI(responses: [
            mockResponse(status: 401, body: "Unauthorized"),
        ])

        await #expect(throws: (any Error).self) {
            let _: Pong = try await api.get("/ping")
        }
        #expect(MockURLProtocol.callCount == 1)
    }

    @Test func throws404ImmediatelyWithoutRetry() async throws {
        let api = makeAPI(responses: [
            mockResponse(status: 404, body: "Not Found"),
        ])

        await #expect(throws: (any Error).self) {
            let _: Pong = try await api.get("/ping")
        }
        #expect(MockURLProtocol.callCount == 1)
    }

    @Test func throws501ImmediatelyWithoutRetry() async throws {
        let api = makeAPI(responses: [
            mockResponse(status: 501, body: "Not Implemented"),
        ])

        await #expect(throws: (any Error).self) {
            let _: Pong = try await api.get("/ping")
        }
        #expect(MockURLProtocol.callCount == 1)
    }

    @Test func retriesOn500ThenSucceeds() async throws {
        // First call returns 500, second returns 200.
        let api = makeAPI(responses: [
            mockResponse(status: 500, body: "Internal Server Error"),
            mockResponse(body: #"{"status":"ok"}"#),
        ])
        let pong: Pong = try await api.get("/ping")
        #expect(pong.status == "ok")
        #expect(MockURLProtocol.callCount == 2)
    }

    @Test func exhaustsAllRetriesOn500() async throws {
        // All 3 attempts return 500.
        let api = makeAPI(responses: [
            mockResponse(status: 500, body: "Error"),
            mockResponse(status: 500, body: "Error"),
            mockResponse(status: 500, body: "Error"),
        ])

        await #expect(throws: (any Error).self) {
            let _: Pong = try await api.get("/ping")
        }
        #expect(MockURLProtocol.callCount == 3)
    }

    @Test func throwsDescriptiveErrorMessageForClientError() async throws {
        let api = makeAPI(responses: [
            mockResponse(status: 403, body: "Forbidden: API key invalid"),
        ])

        do {
            let _: Pong = try await api.get("/ping")
            Issue.record("Expected throw")
        } catch {
            #expect(error.localizedDescription.contains("Forbidden"))
        }
    }

    @Test func throwsHTTPCodeWhenBodyIsEmpty() async throws {
        let api = makeAPI(responses: [
            mockResponse(status: 503, body: "   "),
        ])

        // After 3 retries, should throw with HTTP 503 in description.
        do {
            let _: Pong = try await api.get("/ping")
            Issue.record("Expected throw")
        } catch {
            #expect(error.localizedDescription.contains("503"))
        }
    }

    @Test func throwsOnInvalidJSON() async throws {
        let api = makeAPI(responses: [mockResponse(body: "not valid json")])

        await #expect(throws: (any Error).self) {
            let _: Pong = try await api.get("/ping")
        }
    }

    @MainActor @Test func addsAuthorizationHeaderWhenAPIKeyIsSet() async throws {
        HeaderCapturingProtocol.capturedRequest = nil
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [HeaderCapturingProtocol.self]
        let api = MascaradeAPI(
            baseURL: URL(string: "http://localhost")!,
            apiKey: "my-secret-key",
            session: URLSession(configuration: config)
        )
        let _: Pong = try await api.get("/ping")
        #expect(HeaderCapturingProtocol.capturedRequest?.value(forHTTPHeaderField: "Authorization") == "Bearer my-secret-key")
    }

    @MainActor @Test func noAuthorizationHeaderWhenAPIKeyIsEmpty() async throws {
        HeaderCapturingProtocol.capturedRequest = nil
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [HeaderCapturingProtocol.self]
        let api = MascaradeAPI(
            baseURL: URL(string: "http://localhost")!,
            apiKey: "",
            session: URLSession(configuration: config)
        )
        let _: Pong = try await api.get("/ping")
        #expect(HeaderCapturingProtocol.capturedRequest?.value(forHTTPHeaderField: "Authorization") == nil)
    }
}

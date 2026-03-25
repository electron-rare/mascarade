//
//  CockpitViewModel.swift
//  Mascarade
//
//  Created by Codex on 07/03/2026.
//

import Combine
import SwiftUI

@MainActor
final class CockpitViewModel: ObservableObject {
    @Published private(set) var health: HealthResponse?
    @Published private(set) var summary: OpsSummary?
    @Published private(set) var agents: [AgentSummary] = []
    @Published private(set) var workflows: [WorkflowSummary] = []
    @Published private(set) var bannerMessage: String?
    @Published private(set) var isRefreshing = false
    @Published private(set) var lastRefresh: Date?
    @Published private(set) var connectedBaseURL = ""

    /// TTL du cache: on ne rafraichit pas si le dernier refresh date de moins de 30s.
    private static let cacheTTL: TimeInterval = 30

    var apiIsHealthy: Bool {
        health?.status == "ok"
    }

    var coreIsHealthy: Bool {
        health?.core?.status == "ok" || summary?.monitor.gateway.core == true
    }

    var lastRefreshLabel: String {
        guard let lastRefresh else {
            return "never refreshed"
        }
        return DateFormatter.mascaradeClock.string(from: lastRefresh)
    }

    /// Retourne true si les donnees en cache sont encore fraîches.
    var isCacheFresh: Bool {
        guard let lastRefresh else { return false }
        return Date().timeIntervalSince(lastRefresh) < Self.cacheTTL
    }

    func refresh(using settings: ConnectionSettings, force: Bool = false) async {
        guard !isCacheFresh || force else { return }

        guard let baseURL = settings.resolvedBaseURL() else {
            bannerMessage = "Configure une URL valide avant de rafraichir le cockpit."
            return
        }

        isRefreshing = true
        connectedBaseURL = settings.normalizedBaseURL
        let client = MascaradeAPI(baseURL: baseURL, apiKey: settings.apiKey)

        async let healthResult = capture { try await client.get("/health", as: HealthResponse.self) }
        async let summaryResult = capture { try await client.get("/api/ops/summary", as: OpsSummary.self) }
        async let agentsResult = capture { try await client.get("/api/agents", as: AgentsPayload.self) }
        async let workflowsResult = capture { try await client.get("/api/killlife/workflows", as: WorkflowsPayload.self) }

        let (healthResultValue, summaryResultValue, agentsResultValue, workflowsResultValue) = await (
            healthResult,
            summaryResult,
            agentsResult,
            workflowsResult
        )

        var failures: [String] = []

        switch healthResultValue {
        case .success(let health):
            self.health = health
        case .failure(let error):
            failures.append("health: \(error.localizedDescription)")
        }

        switch summaryResultValue {
        case .success(let summary):
            self.summary = summary
        case .failure(let error):
            failures.append("ops: \(error.localizedDescription)")
        }

        switch agentsResultValue {
        case .success(let payload):
            agents = payload.agents.sorted { $0.name < $1.name }
        case .failure(let error):
            failures.append("agents: \(error.localizedDescription)")
        }

        switch workflowsResultValue {
        case .success(let payload):
            workflows = payload.workflows.sorted { $0.updatedAt > $1.updatedAt }
        case .failure(let error):
            failures.append("killlife: \(error.localizedDescription)")
        }

        bannerMessage = failures.isEmpty ? nil : failures.joined(separator: "  |  ")
        lastRefresh = Date()
        isRefreshing = false
    }

    private func capture<T>(_ operation: @escaping () async throws -> T) async -> Result<T, Error> {
        do {
            return .success(try await operation())
        } catch {
            return .failure(error)
        }
    }
}

private extension DateFormatter {
    static let mascaradeClock: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "fr_FR")
        formatter.dateStyle = .none
        formatter.timeStyle = .short
        return formatter
    }()
}

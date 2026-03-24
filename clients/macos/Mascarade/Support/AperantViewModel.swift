//
//  AperantViewModel.swift
//  Mascarade
//
//  ObservableObject pour l'intégration Aperant.
//  Gère: health, liste des specs, detail d'un spec, création, suppression.
//

import Combine
import Foundation
import SwiftUI

@MainActor
final class AperantViewModel: ObservableObject {
    @Published private(set) var health: AperantHealth?
    @Published private(set) var specs: [AperantSpecSummary] = []
    @Published private(set) var selectedSpec: AperantSpecDetail?
    @Published private(set) var isRefreshing = false
    @Published private(set) var isCreating = false
    @Published private(set) var bannerMessage: String?
    @Published private(set) var lastRefresh: Date?
    @Published private(set) var connectedBaseURL = ""

    private static let cacheTTL: TimeInterval = 30

    var isHealthy: Bool {
        health?.isOk == true
    }

    var isCacheFresh: Bool {
        guard let lastRefresh else { return false }
        return Date().timeIntervalSince(lastRefresh) < Self.cacheTTL
    }

    var lastRefreshLabel: String {
        guard let lastRefresh else { return "jamais" }
        return DateFormatter.aperantClock.string(from: lastRefresh)
    }

    // MARK: - Refresh (health + specs list)

    func refresh(using settings: AperantConnectionSettings, force: Bool = false) async {
        guard !isCacheFresh || force else { return }

        guard let baseURL = settings.resolvedBaseURL() else {
            bannerMessage = "Configure l'URL du bridge Aperant dans les réglages."
            return
        }

        isRefreshing = true
        connectedBaseURL = settings.normalizedBaseURL
        let client = AperantAPI(baseURL: baseURL, apiKey: settings.apiKey)

        async let healthResult = capture { try await client.health() }
        async let specsResult = capture { try await client.listSpecs() }

        let (h, s) = await (healthResult, specsResult)

        var failures: [String] = []

        switch h {
        case .success(let value):
            health = value
        case .failure(let error):
            failures.append("health: \(error.localizedDescription)")
        }

        switch s {
        case .success(let value):
            specs = value
        case .failure(let error):
            failures.append("specs: \(error.localizedDescription)")
        }

        bannerMessage = failures.isEmpty ? nil : failures.joined(separator: "  |  ")
        lastRefresh = Date()
        isRefreshing = false
    }

    // MARK: - Load spec detail

    func loadSpec(_ id: String, using settings: AperantConnectionSettings) async {
        guard let baseURL = settings.resolvedBaseURL() else { return }
        let client = AperantAPI(baseURL: baseURL, apiKey: settings.apiKey)
        switch await capture({ try await client.getSpec(id) }) {
        case .success(let detail):
            selectedSpec = detail
        case .failure(let error):
            bannerMessage = "Impossible de charger le spec: \(error.localizedDescription)"
        }
    }

    func clearSelectedSpec() {
        selectedSpec = nil
    }

    // MARK: - Create spec from vault entry

    func createSpec(
        title: String,
        content: String,
        project: String?,
        vaultEntryId: String?,
        vaultEntryTitle: String?,
        using settings: AperantConnectionSettings
    ) async -> AperantSpecDetail? {
        guard let baseURL = settings.resolvedBaseURL() else {
            bannerMessage = "Configure l'URL du bridge Aperant dans les réglages."
            return nil
        }
        isCreating = true
        defer { isCreating = false }

        let client = AperantAPI(baseURL: baseURL, apiKey: settings.apiKey)
        let context: AperantCreateContext? = vaultEntryId.map {
            AperantCreateContext(
                vaultEntryId: $0,
                vaultEntryTitle: vaultEntryTitle ?? title
            )
        }
        let request = AperantCreateRequest(
            title: title,
            content: content,
            project: project,
            context: context
        )

        switch await capture({ try await client.createSpec(request) }) {
        case .success(let detail):
            // Rafraîchit la liste pour inclure le nouveau spec
            await refresh(using: settings, force: true)
            return detail
        case .failure(let error):
            bannerMessage = "Création échouée: \(error.localizedDescription)"
            return nil
        }
    }

    // MARK: - Delete spec

    func deleteSpec(_ id: String, using settings: AperantConnectionSettings) async {
        guard let baseURL = settings.resolvedBaseURL() else { return }
        let client = AperantAPI(baseURL: baseURL, apiKey: settings.apiKey)
        switch await capture({ try await client.deleteSpec(id) }) {
        case .success:
            specs.removeAll { $0.id == id }
            if selectedSpec?.id == id { selectedSpec = nil }
        case .failure(let error):
            bannerMessage = "Suppression échouée: \(error.localizedDescription)"
        }
    }

    // MARK: - Private

    private func capture<T>(_ operation: @escaping () async throws -> T) async -> Result<T, Error> {
        do {
            return .success(try await operation())
        } catch {
            return .failure(error)
        }
    }
}

private extension DateFormatter {
    static let aperantClock: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.dateStyle = .none
        f.timeStyle = .short
        return f
    }()
}

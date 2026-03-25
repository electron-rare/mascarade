//
//  FrappeViewModel.swift
//  Mascarade
//
//  ObservableObject pour l'intégration Frappe.
//  Gère : ping/health, liste des tâches, projets, todos.
//  Pattern identique à AperantViewModel.
//

import Combine
import Foundation
import SwiftUI

@MainActor
final class FrappeViewModel: ObservableObject {
    @Published private(set) var isOnline: Bool?          // nil = inconnu
    @Published private(set) var tasks: [FrappeTask] = []
    @Published private(set) var projects: [FrappeProject] = []
    @Published private(set) var todos: [FrappeToDo] = []
    @Published private(set) var isRefreshing = false
    @Published private(set) var bannerMessage: String?
    @Published private(set) var lastRefresh: Date?
    @Published private(set) var connectedBaseURL = ""

    // Filtres actifs
    @Published var selectedProjectFilter: String? = nil
    @Published var selectedStatusFilter: String? = nil

    private static let cacheTTL: TimeInterval = 30

    var isCacheFresh: Bool {
        guard let lastRefresh else { return false }
        return Date().timeIntervalSince(lastRefresh) < Self.cacheTTL
    }

    var lastRefreshLabel: String {
        guard let lastRefresh else { return "jamais" }
        return DateFormatter.frappeClock.string(from: lastRefresh)
    }

    var filteredTasks: [FrappeTask] {
        tasks.filter { task in
            let matchProject = selectedProjectFilter == nil || task.project == selectedProjectFilter
            let matchStatus  = selectedStatusFilter  == nil || task.status  == selectedStatusFilter
            return matchProject && matchStatus
        }
    }

    var openTaskCount: Int { tasks.filter { $0.taskStatus != .completed && $0.taskStatus != .cancelled }.count }
    var projectCount: Int  { projects.count }
    var openTodoCount: Int { todos.filter { $0.isOpen }.count }

    // MARK: - Refresh

    func refresh(using settings: FrappeConnectionSettings, force: Bool = false) async {
        guard !isCacheFresh || force else { return }

        guard let baseURL = settings.resolvedBaseURL() else {
            bannerMessage = "Configure l'URL Frappe dans les réglages."
            return
        }

        isRefreshing = true
        connectedBaseURL = settings.normalizedBaseURL
        let client = FrappeAPI(baseURL: baseURL, authHeader: settings.authorizationHeader)

        // Ping + listes en parallèle
        async let pingResult     = capture { try await client.ping() }
        async let tasksResult    = capture { try await client.listTasks() }
        async let projectsResult = capture { try await client.listProjects() }
        async let todosResult    = capture { try await client.listToDos(onlyOpen: true) }

        let (p, t, pr, td) = await (pingResult, tasksResult, projectsResult, todosResult)

        var failures: [String] = []

        switch p {
        case .success(let ping): isOnline = ping.isOk
        case .failure(let err):
            isOnline = false
            failures.append("ping: \(err.localizedDescription)")
        }

        switch t {
        case .success(let value): tasks = value
        case .failure(let err):   failures.append("tâches: \(err.localizedDescription)")
        }

        switch pr {
        case .success(let value): projects = value
        case .failure(let err):   failures.append("projets: \(err.localizedDescription)")
        }

        switch td {
        case .success(let value): todos = value
        case .failure(let err):   failures.append("todos: \(err.localizedDescription)")
        }

        bannerMessage = failures.isEmpty ? nil : failures.joined(separator: "  |  ")
        lastRefresh = Date()
        isRefreshing = false
    }

    // MARK: - Banner (appelé depuis KanbanBoardView)

    func setBanner(_ message: String) {
        bannerMessage = message
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
    static let frappeClock: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.dateStyle = .none
        f.timeStyle = .short
        return f
    }()
}

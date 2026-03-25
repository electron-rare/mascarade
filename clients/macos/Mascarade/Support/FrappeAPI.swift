//
//  FrappeAPI.swift
//  Mascarade
//
//  Client HTTP pour l'API REST Frappe.
//  Auth : "Authorization: token <api_key>:<api_secret>"
//  Pattern identique à AperantAPI — retry exponentiel, 4xx non retentés.
//

import Foundation

struct FrappeAPI {
    let baseURL: URL
    let authHeader: String?
    let session: URLSession
    let retryDelayNanoseconds: UInt64

    private static let maxAttempts = 3

    init(
        baseURL: URL,
        authHeader: String?,
        session: URLSession = .shared,
        retryDelayNanoseconds: UInt64 = 1_000_000_000
    ) {
        self.baseURL = baseURL
        self.authHeader = authHeader
        self.session = session
        self.retryDelayNanoseconds = retryDelayNanoseconds
    }

    // MARK: - Public endpoints

    /// GET /api/method/ping → { "message": "pong" }
    func ping() async throws -> FrappePing {
        try await get("/api/method/ping", as: FrappeResponse<FrappePing>.self).data
    }

    /// GET /api/resource/Task avec filtres
    func listTasks(filters: [[String]] = [], limit: Int = 50) async throws -> [FrappeTask] {
        let params = FrappeListParams(
            doctype: "Task",
            fields: ["name", "subject", "status", "priority", "project",
                     "_assign", "description", "exp_end_date", "modified"],
            filters: filters,
            limitPageLength: limit
        )
        return try await listResource("Task", params: params, as: FrappeTask.self)
    }

    /// GET /api/resource/Project
    func listProjects(limit: Int = 50) async throws -> [FrappeProject] {
        let params = FrappeListParams(
            doctype: "Project",
            fields: ["name", "project_name", "status", "percent_complete",
                     "expected_end_date", "modified"],
            limitPageLength: limit
        )
        return try await listResource("Project", params: params, as: FrappeProject.self)
    }

    /// GET /api/resource/ToDo
    func listToDos(onlyOpen: Bool = true, limit: Int = 50) async throws -> [FrappeToDo] {
        var filters: [[String]] = []
        if onlyOpen {
            filters = [["status", "=", "Open"]]
        }
        let params = FrappeListParams(
            doctype: "ToDo",
            fields: ["name", "description", "status", "priority", "date", "owner", "modified"],
            filters: filters,
            limitPageLength: limit
        )
        return try await listResource("ToDo", params: params, as: FrappeToDo.self)
    }

    // MARK: - Création de tâche

    /// POST /api/resource/Task → crée une nouvelle tâche, retourne le nom Frappe créé
    @discardableResult
    func createTask(
        subject: String,
        status: String = "Open",
        priority: String? = nil,
        project: String? = nil,
        description: String? = nil,
        expEndDate: String? = nil   // format "YYYY-MM-DD"
    ) async throws -> String {
        guard let url = URL(string: baseURL.absoluteString + "/api/resource/Task") else {
            throw FrappeAPIError("URL invalide pour POST Task.")
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = 20
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyHeaders(to: &req)

        var body: [String: Any] = ["subject": subject, "status": status]
        if let priority, !priority.isEmpty     { body["priority"]     = priority }
        if let project, !project.isEmpty       { body["project"]      = project }
        if let description, !description.isEmpty { body["description"] = description }
        if let expEndDate, !expEndDate.isEmpty { body["exp_end_date"] = expEndDate }

        req.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else {
            throw FrappeAPIError("Réponse HTTP invalide.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let msg = extractFrappeError(from: data) ?? "HTTP \(http.statusCode)"
            throw FrappeAPIError(msg)
        }
        // Retourne le nom Frappe (ex: "TASK-2026-00005")
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let dataObj = json["data"] as? [String: Any],
           let name = dataObj["name"] as? String {
            return name
        }
        return ""
    }

    // MARK: - PATCH status tâche

    /// PUT /api/resource/Task/{name}  → met à jour le champ status
    func updateTaskStatus(name: String, status: String) async throws {
        guard let url = URL(string: baseURL.absoluteString + "/api/resource/Task/\(name)") else {
            throw FrappeAPIError("URL invalide pour PATCH Task/\(name).")
        }
        var req = URLRequest(url: url)
        req.httpMethod = "PUT"
        req.timeoutInterval = 20
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        applyHeaders(to: &req)

        let body = ["status": status]
        req.httpBody = try JSONSerialization.data(withJSONObject: ["data": body])

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else {
            throw FrappeAPIError("Réponse HTTP invalide.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let msg = extractFrappeError(from: data) ?? "HTTP \(http.statusCode)"
            throw FrappeAPIError(msg)
        }
    }

    // MARK: - Generic list

    private func listResource<T: Decodable>(
        _ doctype: String,
        params: FrappeListParams,
        as type: T.Type
    ) async throws -> [T] {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/resource/\(doctype)"), resolvingAgainstBaseURL: false)
        components?.queryItems = params.queryItems

        guard let url = components?.url else {
            throw FrappeAPIError("URL invalide pour /api/resource/\(doctype).")
        }

        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        req.timeoutInterval = 20
        applyHeaders(to: &req)

        return try await execute(req, as: FrappeListResponse<T>.self, path: "/api/resource/\(doctype)").data
    }

    // MARK: - Generic GET

    private func get<T: Decodable>(_ path: String, as type: T.Type) async throws -> T {
        guard let url = URL(string: baseURL.absoluteString + path) else {
            throw FrappeAPIError("URL invalide pour \(path).")
        }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        req.timeoutInterval = 20
        applyHeaders(to: &req)
        return try await execute(req, as: T.self, path: path)
    }

    // MARK: - Execution avec retry

    private func execute<T: Decodable>(
        _ request: URLRequest,
        as type: T.Type,
        path: String
    ) async throws -> T {
        var lastError: Error = FrappeAPIError("Aucune tentative effectuée.")

        for attempt in 0..<Self.maxAttempts {
            if attempt > 0 {
                let delay = UInt64(attempt) * retryDelayNanoseconds
                if delay > 0 { try await Task.sleep(nanoseconds: delay) }
            }

            do {
                let (data, response) = try await session.data(for: request)
                guard let http = response as? HTTPURLResponse else {
                    throw FrappeAPIError("Réponse HTTP invalide.")
                }
                guard (200..<300).contains(http.statusCode) else {
                    let msg = extractFrappeError(from: data) ?? "HTTP \(http.statusCode)"
                    let error = FrappeAPIError(msg)
                    // 4xx → pas de retry
                    if (400..<500).contains(http.statusCode) {
                        throw error
                    }
                    lastError = error
                    continue
                }
                do {
                    return try decoder.decode(T.self, from: data)
                } catch {
                    throw FrappeAPIError("Décodage JSON impossible pour \(path): \(error.localizedDescription)")
                }
            } catch let error as FrappeAPIError {
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
        if let auth = authHeader {
            request.setValue(auth, forHTTPHeaderField: "Authorization")
        }
    }

    private var decoder: JSONDecoder {
        // FrappeTask / FrappeProject etc. ont des CodingKeys explicites.
        // Ne pas utiliser .convertFromSnakeCase qui entrerait en conflit
        // avec les CodingKeys déjà définis (double-conversion des clés JSON).
        JSONDecoder()
    }

    /// Tente d'extraire le message d'erreur Frappe depuis la réponse JSON.
    private func extractFrappeError(from data: Data) -> String? {
        if let body = try? JSONDecoder().decode(FrappeErrorResponse.self, from: data),
           let exc = body.excType, !exc.isEmpty {
            return exc
        }
        return String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .nilIfEmpty
    }
}

// MARK: - Error

struct FrappeAPIError: LocalizedError {
    private let message: String

    init(_ message: String) {
        self.message = message
    }

    var errorDescription: String? { message }
}

private extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}

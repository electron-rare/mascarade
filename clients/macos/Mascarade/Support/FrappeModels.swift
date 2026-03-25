//
//  FrappeModels.swift
//  Mascarade
//
//  Structs Decodable/Encodable pour l'API REST Frappe.
//  Endpoints : /api/resource/{DocType}
//              /api/method/frappe.client.get_list
//              /api/method/ping
//

import Foundation

// MARK: - Enveloppe générique Frappe

/// Frappe enveloppe toujours les réponses dans { "data": ... }
struct FrappeResponse<T: Decodable>: Decodable {
    let data: T
}

/// Réponse de liste Frappe : { "data": [...] }
struct FrappeListResponse<T: Decodable>: Decodable {
    let data: [T]
}

// MARK: - Ping / health

nonisolated struct FrappePing: Decodable {
    let message: String
    var isOk: Bool { message == "pong" }
}

// MARK: - DocType : Task

nonisolated struct FrappeTask: Decodable, Identifiable {
    let name: String               // Frappe ID (ex: "TASK-2026-00001")
    let subject: String
    let status: String
    let priority: String?
    let project: String?
    let assign: String?            // JSON texte : ["user@email"] ou null
    let description: String?
    let expEndDate: String?        // date d'échéance (colonne exp_end_date)
    let modified: String?

    var id: String { name }

    var taskStatus: FrappeTaskStatus {
        FrappeTaskStatus(rawValue: status) ?? .open
    }

    /// Premier assigné extrait du champ _assign (JSON array en texte)
    var firstAssignee: String? {
        guard let raw = assign,
              let data = raw.data(using: .utf8),
              let arr = try? JSONDecoder().decode([String].self, from: data),
              let first = arr.first else { return nil }
        return first
    }

    enum CodingKeys: String, CodingKey {
        case name, subject, status, priority, project, description, modified
        case assign    = "_assign"
        case expEndDate = "exp_end_date"
    }
}

enum FrappeTaskStatus: String, CaseIterable, Identifiable {
    var id: String { rawValue }
    case open       = "Open"
    case working    = "Working"
    case pendingReview = "Pending Review"
    case overdue    = "Overdue"
    case template   = "Template"
    case cancelled  = "Cancelled"
    case completed  = "Completed"

    var label: String {
        switch self {
        case .open:          "Ouvert"
        case .working:       "En cours"
        case .pendingReview: "En révision"
        case .overdue:       "En retard"
        case .template:      "Modèle"
        case .cancelled:     "Annulé"
        case .completed:     "Terminé"
        }
    }

    var systemImage: String {
        switch self {
        case .open:          "circle"
        case .working:       "arrow.trianglehead.2.clockwise.rotate.90"
        case .pendingReview: "eye"
        case .overdue:       "exclamationmark.triangle"
        case .template:      "doc.on.doc"
        case .cancelled:     "xmark.circle"
        case .completed:     "checkmark.circle.fill"
        }
    }
}

// MARK: - DocType : Project

nonisolated struct FrappeProject: Decodable, Identifiable {
    let name: String
    let projectName: String
    let status: String
    let percentComplete: Double?
    let expectedEndDate: String?
    let modified: String?

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name, status
        case projectName       = "project_name"
        case percentComplete   = "percent_complete"
        case expectedEndDate   = "expected_end_date"
        case modified
    }
}

// MARK: - DocType : ToDo

nonisolated struct FrappeToDo: Decodable, Identifiable {
    let name: String
    let description: String
    let status: String
    let priority: String?
    let date: String?
    let owner: String?
    let modified: String?

    var id: String { name }

    var isOpen: Bool { status == "Open" }
}

// MARK: - Frappe List Filters (pour requêtes filtrées)

struct FrappeListParams {
    var doctype: String
    var fields: [String]
    var filters: [[String]]
    var orderBy: String
    var limitPageLength: Int

    init(
        doctype: String,
        fields: [String] = ["name", "modified"],
        filters: [[String]] = [],
        orderBy: String = "modified desc",
        limitPageLength: Int = 50
    ) {
        self.doctype = doctype
        self.fields = fields
        self.filters = filters
        self.orderBy = orderBy
        self.limitPageLength = limitPageLength
    }

    /// Construit les query parameters pour /api/resource/{doctype}
    var queryItems: [URLQueryItem] {
        var items: [URLQueryItem] = []
        if let fieldsJSON = try? JSONSerialization.data(withJSONObject: fields),
           let fieldsStr = String(data: fieldsJSON, encoding: .utf8) {
            items.append(URLQueryItem(name: "fields", value: fieldsStr))
        }
        if !filters.isEmpty,
           let filtersJSON = try? JSONSerialization.data(withJSONObject: filters),
           let filtersStr = String(data: filtersJSON, encoding: .utf8) {
            items.append(URLQueryItem(name: "filters", value: filtersStr))
        }
        items.append(URLQueryItem(name: "order_by", value: orderBy))
        items.append(URLQueryItem(name: "limit_page_length", value: String(limitPageLength)))
        return items
    }
}

// MARK: - Frappe Error response

struct FrappeErrorResponse: Decodable {
    let exc: String?
    let excType: String?

    enum CodingKeys: String, CodingKey {
        case exc
        case excType = "exc_type"
    }
}

//
//  AperantModels.swift
//  Mascarade
//
//  Structs Decodable correspondant aux réponses du bridge aperant-bridge.
//

import Foundation

// MARK: - Health

nonisolated struct AperantHealth: Decodable {
    let status: String
    let specsDir: String
    let specsDirExists: Bool
    let specsCount: Int
    let timestamp: String

    var isOk: Bool { status == "ok" }
}

// MARK: - Spec list

nonisolated struct AperantSpecSummary: Decodable, Identifiable {
    let id: String
    let title: String
    let project: String?
    let status: String
    let createdAt: String
    let updatedAt: String

    var specStatus: AperantSpecStatus {
        AperantSpecStatus(rawValue: status) ?? .unknown
    }
}

// MARK: - Spec detail

nonisolated struct AperantSpecDetail: Decodable, Identifiable {
    let id: String
    let title: String
    let project: String?
    let content: String
    let status: String
    let plan: AperantPlan?
    let context: AperantContext?
    let createdAt: String
    let updatedAt: String

    var specStatus: AperantSpecStatus {
        AperantSpecStatus(rawValue: status) ?? .unknown
    }
}

// MARK: - Plan (implementation_plan.json)

nonisolated struct AperantPlan: Decodable {
    let phases: [AperantPhase]?
    let summary: String?
    let estimatedComplexity: String?
}

nonisolated struct AperantPhase: Decodable, Identifiable {
    let phaseId: String?
    let name: String
    let description: String?
    let tasks: [AperantTask]?

    var id: String { phaseId ?? name }

    enum CodingKeys: String, CodingKey {
        case phaseId = "id"
        case name, description, tasks
    }
}

nonisolated struct AperantTask: Decodable, Identifiable {
    let taskId: String?
    let description: String
    let status: String?

    var id: String { taskId ?? description }

    enum CodingKeys: String, CodingKey {
        case taskId = "id"
        case description, status
    }
}

// MARK: - Context

nonisolated struct AperantContext: Decodable {
    let vaultEntryId: String?
    let vaultEntryTitle: String?
    let extra: [String: String]?
}

// MARK: - Create request payload (Encodable)

struct AperantCreateRequest: Encodable {
    let title: String
    let content: String
    let project: String?
    let context: AperantCreateContext?
}

struct AperantCreateContext: Encodable {
    let vaultEntryId: String
    let vaultEntryTitle: String
}

// MARK: - Status enum

enum AperantSpecStatus: String, CaseIterable {
    case pending
    case running
    case done
    case failed
    case unknown

    var label: String {
        switch self {
        case .pending: "En attente"
        case .running: "En cours"
        case .done:    "Terminé"
        case .failed:  "Échoué"
        case .unknown: "Inconnu"
        }
    }

    var systemImage: String {
        switch self {
        case .pending: "clock"
        case .running: "arrow.trianglehead.2.clockwise.rotate.90"
        case .done:    "checkmark.circle"
        case .failed:  "xmark.circle"
        case .unknown: "questionmark.circle"
        }
    }
}

//
//  EntryDraft.swift
//  Mascarade
//

import CoreData
import Foundation

enum EntryKind: String, CaseIterable, Identifiable {
    case plan
    case task
    case doc
    case note

    var id: String { rawValue }

    var title: String {
        switch self {
        case .plan:
            "Plan"
        case .task:
            "Task"
        case .doc:
            "Doc"
        case .note:
            "Note"
        }
    }

    var systemImage: String {
        switch self {
        case .plan:
            "map"
        case .task:
            "checklist"
        case .doc:
            "doc.text"
        case .note:
            "note.text"
        }
    }
}

enum EntryStatus: String, CaseIterable, Identifiable {
    case backlog
    case active
    case blocked
    case done

    var id: String { rawValue }

    var title: String {
        rawValue.capitalized
    }
}

enum EntryStatusFilter: String, CaseIterable, Identifiable {
    case all
    case backlog
    case active
    case blocked
    case done

    var id: String { rawValue }

    var title: String {
        switch self {
        case .all:
            "Tout"
        case .backlog:
            "Backlog"
        case .active:
            "Actif"
        case .blocked:
            "Bloque"
        case .done:
            "Done"
        }
    }

    var entryStatus: EntryStatus? {
        switch self {
        case .all:
            nil
        case .backlog:
            .backlog
        case .active:
            .active
        case .blocked:
            .blocked
        case .done:
            .done
        }
    }
}

struct EntryDraft: Identifiable, Equatable {
    var id: NSManagedObjectID?
    var project: String
    var entryKind: EntryKind
    var status: EntryStatus
    var title: String
    var content: String
    var contentType: String
    var source: String
    var agentWritable: Bool

    static let empty = EntryDraft(
        id: nil,
        project: "Mascarade",
        entryKind: .note,
        status: .active,
        title: "",
        content: "",
        contentType: "text/markdown",
        source: "user",
        agentWritable: true
    )

    init(
        id: NSManagedObjectID? = nil,
        project: String,
        entryKind: EntryKind,
        status: EntryStatus,
        title: String,
        content: String,
        contentType: String,
        source: String,
        agentWritable: Bool
    ) {
        self.id = id
        self.project = project
        self.entryKind = entryKind
        self.status = status
        self.title = title
        self.content = content
        self.contentType = contentType
        self.source = source
        self.agentWritable = agentWritable
    }

    init(project: String) {
        self.init(
            id: nil,
            project: project,
            entryKind: .note,
            status: .active,
            title: "",
            content: "",
            contentType: "text/markdown",
            source: "user",
            agentWritable: true
        )
    }

    init(entry: VaultEntry) {
        id = entry.objectID
        project = entry.safeProject
        entryKind = entry.safeEntryKind
        status = entry.safeStatus
        title = entry.safeTitle
        content = entry.content ?? ""
        contentType = entry.contentType ?? "text/markdown"
        source = entry.safeSource
        agentWritable = entry.agentWritable
    }
}

//
//  VaultEntry.swift
//  Mascarade
//

import CoreData
import Foundation

extension VaultEntry {
    var safeProject: String {
        project?.nonEmpty ?? "Mascarade"
    }

    var safeEntryKind: EntryKind {
        EntryKind(rawValue: entryKind ?? "") ?? .note
    }

    var safeStatus: EntryStatus {
        EntryStatus(rawValue: status ?? "") ?? .active
    }

    var safeTitle: String {
        title?.nonEmpty ?? "Untitled"
    }

    var safeSource: String {
        source?.nonEmpty ?? "user"
    }

    var previewLine: String {
        let collapsed = (content ?? "")
            .replacingOccurrences(of: "\n", with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return collapsed.isEmpty ? "Aucun contenu." : String(collapsed.prefix(160))
    }
}

private extension String {
    var nonEmpty: String? {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

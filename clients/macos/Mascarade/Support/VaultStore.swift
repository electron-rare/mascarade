//
//  VaultStore.swift
//  Mascarade
//

import CoreData
import Foundation

enum VaultStoreError: LocalizedError {
    case emptyTitle
    case missingEntry

    var errorDescription: String? {
        switch self {
        case .emptyTitle:
            return "Le titre ne peut pas etre vide."
        case .missingEntry:
            return "Cette entree n'existe plus dans le store local."
        }
    }
}

struct VaultStore {
    func saveEntry(from draft: EntryDraft, in context: NSManagedObjectContext) throws {
        let trimmedTitle = draft.title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else {
            throw VaultStoreError.emptyTitle
        }

        let entry = try entry(for: draft, in: context)
        let now = Date()

        if entry.createdAt == nil {
            entry.id = UUID()
            entry.createdAt = now
            entry.isArchived = false
        }

        entry.title = trimmedTitle
        entry.project = draft.project.trimmingCharacters(in: .whitespacesAndNewlines).nonEmpty ?? "Mascarade"
        entry.entryKind = draft.entryKind.rawValue
        entry.status = draft.status.rawValue
        entry.content = draft.content.trimmingCharacters(in: .whitespacesAndNewlines)
        entry.contentType = draft.contentType.trimmingCharacters(in: .whitespacesAndNewlines).nonEmpty ?? "text/markdown"
        entry.source = draft.source.trimmingCharacters(in: .whitespacesAndNewlines).nonEmpty ?? "user"
        entry.agentWritable = draft.agentWritable
        entry.updatedAt = now

        if context.hasChanges {
            try context.save()
        }
    }

    func archive(_ entry: VaultEntry, in context: NSManagedObjectContext) throws {
        entry.isArchived = true
        entry.updatedAt = .now
        try context.save()
    }

    func restore(_ entry: VaultEntry, in context: NSManagedObjectContext) throws {
        entry.isArchived = false
        entry.updatedAt = .now
        try context.save()
    }

    func updateStatus(_ entry: VaultEntry, to status: EntryStatus, in context: NSManagedObjectContext) throws {
        entry.status = status.rawValue
        entry.updatedAt = .now
        if context.hasChanges {
            try context.save()
        }
    }

    func delete(_ entry: VaultEntry, in context: NSManagedObjectContext) throws {
        context.delete(entry)
        try context.save()
    }

    func fetchEntry(id: NSManagedObjectID, in context: NSManagedObjectContext) throws -> VaultEntry? {
        try context.existingObject(with: id) as? VaultEntry
    }

    func fetchEntries(
        in context: NSManagedObjectContext,
        searchText: String? = nil,
        includeArchived: Bool = true,
        limit: Int? = nil
    ) throws -> [VaultEntry] {
        let request = VaultEntry.fetchRequest()
        request.sortDescriptors = [NSSortDescriptor(keyPath: \VaultEntry.updatedAt, ascending: false)]

        var predicates: [NSPredicate] = []

        if !includeArchived {
            predicates.append(NSPredicate(format: "isArchived == NO"))
        }

        if let searchText, let trimmed = searchText.nonEmpty {
            let escaped = trimmed
                .replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "*", with: "\\*")
                .replacingOccurrences(of: "?", with: "\\?")
            let pattern = "*\(escaped)*"
            predicates.append(
                NSCompoundPredicate(orPredicateWithSubpredicates: [
                    NSPredicate(format: "title LIKE[cd] %@", pattern),
                    NSPredicate(format: "content LIKE[cd] %@", pattern),
                    NSPredicate(format: "project LIKE[cd] %@", pattern),
                    NSPredicate(format: "source LIKE[cd] %@", pattern)
                ])
            )
        }

        if !predicates.isEmpty {
            request.predicate = NSCompoundPredicate(andPredicateWithSubpredicates: predicates)
        }

        if let limit {
            request.fetchLimit = limit
        }

        return try context.fetch(request)
    }

    private func entry(for draft: EntryDraft, in context: NSManagedObjectContext) throws -> VaultEntry {
        guard let id = draft.id else {
            return VaultEntry(context: context)
        }

        guard let entry = try context.existingObject(with: id) as? VaultEntry else {
            throw VaultStoreError.missingEntry
        }

        return entry
    }
}

private extension String {
    var nonEmpty: String? {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

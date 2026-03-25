//
//  VaultStoreTests.swift
//  MascaradeTests
//

import CoreData
import Testing
@testable import Mascarade

// MARK: - Helpers

@MainActor
private func makeContext() -> NSManagedObjectContext {
    PersistenceController(inMemory: true).container.viewContext
}

private func makeDraft(
    title: String = "Test entry",
    project: String = "Mascarade",
    status: EntryStatus = .active,
    kind: EntryKind = .note,
    content: String = ""
) -> EntryDraft {
    EntryDraft(
        id: nil,
        project: project,
        entryKind: kind,
        status: status,
        title: title,
        content: content,
        contentType: "text/markdown",
        source: "test",
        agentWritable: false
    )
}

// MARK: - VaultStore CRUD tests

@MainActor
struct VaultStoreTests {
    let store = VaultStore()

    // MARK: Save

    @Test func savesNewEntry() throws {
        let ctx = makeContext()
        let draft = makeDraft(title: "Mon entree")
        try store.saveEntry(from: draft, in: ctx)

        let entries = try store.fetchEntries(in: ctx)
        #expect(entries.count == 1)
        #expect(entries.first?.title == "Mon entree")
    }

    @Test func saveTrimsTitle() throws {
        let ctx = makeContext()
        let draft = makeDraft(title: "  Titre avec espaces  ")
        try store.saveEntry(from: draft, in: ctx)

        let entries = try store.fetchEntries(in: ctx)
        #expect(entries.first?.title == "Titre avec espaces")
    }

    @Test func saveSetsDefaultProject() throws {
        let ctx = makeContext()
        let draft = makeDraft(title: "Sans projet", project: "   ")
        try store.saveEntry(from: draft, in: ctx)

        let entries = try store.fetchEntries(in: ctx)
        #expect(entries.first?.project == "Mascarade")
    }

    @Test func saveThrowsOnEmptyTitle() throws {
        let ctx = makeContext()
        let draft = makeDraft(title: "   ")
        #expect(throws: VaultStoreError.emptyTitle) {
            try store.saveEntry(from: draft, in: ctx)
        }
    }

    @Test func saveAssignsUUID() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first
        #expect(entry?.id != nil)
    }

    @Test func saveAssignsTimestamps() throws {
        let ctx = makeContext()
        let before = Date()
        try store.saveEntry(from: makeDraft(), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first
        #expect(entry?.createdAt != nil)
        #expect(entry?.updatedAt != nil)
        if let createdAt = entry?.createdAt {
            #expect(createdAt >= before)
        }
    }

    @Test func saveSetsIsArchivedFalseOnCreate() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first
        #expect(entry?.isArchived == false)
    }

    @Test func updatesExistingEntry() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(title: "Original"), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first!

        var updated = EntryDraft(entry: entry)
        updated.title = "Modifie"
        try store.saveEntry(from: updated, in: ctx)

        let entries = try store.fetchEntries(in: ctx)
        #expect(entries.count == 1)
        #expect(entries.first?.title == "Modifie")
    }

    // MARK: Archive / Restore

    @Test func archivesEntry() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first!

        try store.archive(entry, in: ctx)
        #expect(entry.isArchived == true)
    }

    @Test func restoresArchivedEntry() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first!

        try store.archive(entry, in: ctx)
        try store.restore(entry, in: ctx)
        #expect(entry.isArchived == false)
    }

    @Test func archiveUpdatesTimestamp() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first!
        let before = entry.updatedAt!

        try store.archive(entry, in: ctx)
        #expect(entry.updatedAt! >= before)
    }

    // MARK: Delete

    @Test func deletesEntry() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first!

        try store.delete(entry, in: ctx)
        let entries = try store.fetchEntries(in: ctx)
        #expect(entries.isEmpty)
    }

    @Test func deleteSecondEntry() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(title: "A"), in: ctx)
        try store.saveEntry(from: makeDraft(title: "B"), in: ctx)

        var all = try store.fetchEntries(in: ctx)
        #expect(all.count == 2)

        try store.delete(all[0], in: ctx)
        all = try store.fetchEntries(in: ctx)
        #expect(all.count == 1)
    }

    // MARK: Fetch with filters

    @Test func fetchExcludesArchivedByDefault() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(title: "Live"), in: ctx)
        let archived = try store.fetchEntries(in: ctx).first!
        try store.archive(archived, in: ctx)

        let live = try store.fetchEntries(in: ctx, includeArchived: false)
        #expect(live.isEmpty)
    }

    @Test func fetchIncludesArchivedWhenRequested() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first!
        try store.archive(entry, in: ctx)

        let all = try store.fetchEntries(in: ctx, includeArchived: true)
        #expect(all.count == 1)
    }

    @Test func fetchSearchFiltersOnTitle() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(title: "Alpha"), in: ctx)
        try store.saveEntry(from: makeDraft(title: "Beta"), in: ctx)

        let results = try store.fetchEntries(in: ctx, searchText: "alph")
        #expect(results.count == 1)
        #expect(results.first?.title == "Alpha")
    }

    @Test func fetchSearchFiltersOnProject() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(title: "T1", project: "Kill_LIFE"), in: ctx)
        try store.saveEntry(from: makeDraft(title: "T2", project: "Mascarade"), in: ctx)

        let results = try store.fetchEntries(in: ctx, searchText: "Kill")
        #expect(results.count == 1)
        #expect(results.first?.project == "Kill_LIFE")
    }

    @Test func fetchLimitIsRespected() throws {
        let ctx = makeContext()
        for i in 1...5 {
            try store.saveEntry(from: makeDraft(title: "Entry \(i)"), in: ctx)
        }

        let limited = try store.fetchEntries(in: ctx, limit: 3)
        #expect(limited.count == 3)
    }

    // MARK: fetchEntry by ID

    @Test func fetchEntryByIDReturnsCorrectEntry() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(title: "Target"), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first!

        let fetched = try store.fetchEntry(id: entry.objectID, in: ctx)
        #expect(fetched?.title == "Target")
    }

    // MARK: updateStatus

    @Test func updateStatusChangesStatus() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(title: "Todo", status: .backlog), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first!

        try store.updateStatus(entry, to: .active, in: ctx)
        #expect(entry.safeStatus == .active)
    }

    @Test func updateStatusUpdatesTimestamp() throws {
        let ctx = makeContext()
        try store.saveEntry(from: makeDraft(title: "Todo", status: .backlog), in: ctx)
        let entry = try store.fetchEntries(in: ctx).first!
        let before = entry.updatedAt ?? .distantPast

        try store.updateStatus(entry, to: .done, in: ctx)
        let after = entry.updatedAt ?? .distantPast
        #expect(after >= before)
    }
}

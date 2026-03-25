//
//  MascaradeTests.swift
//  MascaradeTests
//
//  Created by Clément SAILLANT on 07/03/2026.
//

import CoreData
import Testing
@testable import Mascarade

struct MascaradeTests {

    @Test func trimsBaseURLWhitespaceAndTrailingSlash() async throws {
        #expect(ConnectionSettings.normalizedBaseURL("  http://127.0.0.1:3100/  ") == "http://127.0.0.1:3100")
    }

    @Test func keepsEmptyBaseURLEmpty() async throws {
        #expect(ConnectionSettings.normalizedBaseURL("   ") == "")
    }

    @MainActor
    @Test func seedsLocalCockpitOnlyOnce() throws {
        let controller = PersistenceController(inMemory: true)

        try controller.seedIfNeeded()
        try controller.seedIfNeeded()

        let request = NSFetchRequest<NSFetchRequestResult>(entityName: "VaultEntry")
        let count = try controller.container.viewContext.count(for: request)

        #expect(count == PlanningTemplates.mascaradePack.count)
    }
}

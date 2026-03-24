//
//  MascaradeApp.swift
//  Mascarade
//
//  Created by Clément SAILLANT on 07/03/2026.
//

import SwiftUI

@main
@MainActor
struct MascaradeApp: App {
    @StateObject private var persistenceController: PersistenceController

    init() {
        let inMemory = ProcessInfo.processInfo.arguments.contains("--ui-testing")
        _persistenceController = StateObject(
            wrappedValue: PersistenceController(inMemory: inMemory)
        )
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(\.managedObjectContext, persistenceController.container.viewContext)
                .environmentObject(persistenceController)
        }
    }
}

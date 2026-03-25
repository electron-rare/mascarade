//
//  Persistence.swift
//  Mascarade
//

import Combine
import CoreData

enum SyncStatus: Equatable {
    case localOnly(reason: String)
    case error(message: String)

    var title: String {
        switch self {
        case .localOnly:
            return "Cockpit local"
        case .error:
            return "Store indisponible"
        }
    }

    var message: String {
        switch self {
        case .localOnly(let reason):
            return reason
        case .error(let message):
            return message
        }
    }

    var systemImage: String {
        switch self {
        case .localOnly:
            return "externaldrive"
        case .error:
            return "externaldrive.badge.exclamationmark"
        }
    }
}

@MainActor
final class PersistenceController: ObservableObject {
    @Published private(set) var loadErrorMessage: String?
    @Published private(set) var syncStatus: SyncStatus

    static let preview = PersistenceController(inMemory: true)

    let container: NSPersistentContainer

    private let templateService = TemplateUpsertService()
    private let store = VaultStore()

    init(inMemory: Bool = false) {
        syncStatus = inMemory
            ? .localOnly(reason: "Store en memoire pour previews et tests.")
            : .localOnly(reason: "Le cockpit Mascarade tourne en local. La synchro cloud sera recablee apres le socle offline-first.")
        container = NSPersistentContainer(name: "MascaradeModel")

        guard let storeDescription = container.persistentStoreDescriptions.first else {
            loadErrorMessage = "Description du store absente."
            syncStatus = .error(message: loadErrorMessage ?? "Description du store absente.")
            return
        }

        if inMemory {
            storeDescription.url = URL(fileURLWithPath: "/dev/null")
        }

        storeDescription.shouldMigrateStoreAutomatically = true
        storeDescription.shouldInferMappingModelAutomatically = true

        container.viewContext.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy
        container.viewContext.automaticallyMergesChangesFromParent = true

        container.loadPersistentStores { [weak self] _, error in
            guard let self else {
                return
            }

            if let error = error as NSError? {
                let message = [
                    "Impossible de charger le store local.",
                    error.localizedDescription
                ].joined(separator: " ")

                Task { @MainActor [weak self] in
                    self?.loadErrorMessage = message
                    self?.syncStatus = .error(message: message)
                }
                return
            }

            Task { @MainActor [weak self] in
                do {
                    try self?.seedIfNeeded()
                } catch {
                    let message = "Le seed initial du cockpit a echoue. \(error.localizedDescription)"
                    self?.loadErrorMessage = message
                    self?.syncStatus = .error(message: message)
                }
            }
        }
    }

    func seedIfNeeded() throws {
        let request = NSFetchRequest<NSFetchRequestResult>(entityName: "VaultEntry")
        request.fetchLimit = 1

        guard try container.viewContext.count(for: request) == 0 else {
            return
        }

        try templateService.upsert(PlanningTemplates.mascaradePack, in: container.viewContext, store: store)
    }
}

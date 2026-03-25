//
//  ConnectionSettings.swift
//  Mascarade
//
//  Created by Codex on 07/03/2026.
//

import Combine
import Foundation
import Security

@MainActor
final class ConnectionSettings: ObservableObject {
    private enum Keys {
        static let baseURL = "mascarade.base-url"
        static let savedAt = "mascarade.saved-at"
        // API key est stockee dans le Keychain, pas dans UserDefaults.
        static let keychainAccount = "mascarade-api-key"
        static let keychainService = Bundle.main.bundleIdentifier ?? "fr.lelectronrare.mascarade"
    }

    @Published var baseURL: String
    @Published private(set) var apiKeyIsSet: Bool
    @Published private(set) var lastSavedAt: Date?

    private let defaults: UserDefaults

    // Expose la cle pour MascaradeAPI (lecture uniquement, jamais affichee).
    private(set) var apiKey: String = ""

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        self.baseURL = defaults.string(forKey: Keys.baseURL) ?? "http://127.0.0.1:3100"
        self.lastSavedAt = defaults.object(forKey: Keys.savedAt) as? Date
        let stored = Self.readKeychain()
        self.apiKey = stored ?? ""
        self.apiKeyIsSet = stored != nil && !(stored?.isEmpty ?? true)
    }

    var normalizedBaseURL: String {
        Self.normalizedBaseURL(baseURL)
    }

    var lastSavedAtLabel: String {
        guard let lastSavedAt else {
            return "never"
        }
        return DateFormatter.mascaradeClock.string(from: lastSavedAt)
    }

    func update(baseURL: String, apiKey rawKey: String) {
        self.baseURL = Self.normalizedBaseURL(baseURL)
        self.lastSavedAt = Date()

        defaults.set(self.baseURL, forKey: Keys.baseURL)
        defaults.set(self.lastSavedAt, forKey: Keys.savedAt)

        let trimmed = rawKey.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            Self.deleteKeychain()
            self.apiKey = ""
            self.apiKeyIsSet = false
        } else {
            Self.writeKeychain(trimmed)
            self.apiKey = trimmed
            self.apiKeyIsSet = true
        }
    }

    func resolvedBaseURL() -> URL? {
        URL(string: normalizedBaseURL)
    }

    nonisolated static func normalizedBaseURL(_ rawValue: String) -> String {
        var value = rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
        while value.hasSuffix("/") {
            value.removeLast()
        }
        return value
    }

    // MARK: - Keychain helpers (nonisolated, thread-safe)

    private static func writeKeychain(_ value: String) {
        guard let data = value.data(using: .utf8) else { return }
        deleteKeychain()
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: Keys.keychainService,
            kSecAttrAccount as String: Keys.keychainAccount,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        ]
        SecItemAdd(query as CFDictionary, nil)
    }

    private static func readKeychain() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: Keys.keychainService,
            kSecAttrAccount as String: Keys.keychainAccount,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    @discardableResult
    private static func deleteKeychain() -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: Keys.keychainService,
            kSecAttrAccount as String: Keys.keychainAccount,
        ]
        return SecItemDelete(query as CFDictionary) == errSecSuccess
    }
}

private extension DateFormatter {
    static let mascaradeClock: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "fr_FR")
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        return formatter
    }()
}

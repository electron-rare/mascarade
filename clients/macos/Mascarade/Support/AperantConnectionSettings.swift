//
//  AperantConnectionSettings.swift
//  Mascarade
//
//  Réglages de connexion pour le bridge Aperant.
//  URL stockée dans UserDefaults, clé API dans le Keychain.
//  Même pattern que ConnectionSettings.
//

import Combine
import Foundation
import Security

@MainActor
final class AperantConnectionSettings: ObservableObject {
    private enum Keys {
        static let baseURL = "aperant.bridge-url"
        static let savedAt = "aperant.saved-at"
        static let keychainAccount = "aperant-bridge-api-key"
        static let keychainService = Bundle.main.bundleIdentifier ?? "fr.lelectronrare.mascarade"
    }

    @Published var baseURL: String
    @Published private(set) var apiKeyIsSet: Bool
    @Published private(set) var lastSavedAt: Date?

    private let defaults: UserDefaults
    private(set) var apiKey: String = ""

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        self.baseURL = defaults.string(forKey: Keys.baseURL) ?? "http://tower:3200"
        self.lastSavedAt = defaults.object(forKey: Keys.savedAt) as? Date
        let stored = Self.readKeychain()
        self.apiKey = stored ?? ""
        self.apiKeyIsSet = stored != nil && !(stored?.isEmpty ?? true)
    }

    var normalizedBaseURL: String {
        Self.normalizeURL(baseURL)
    }

    var lastSavedAtLabel: String {
        guard let lastSavedAt else { return "jamais" }
        return DateFormatter.aperantSettingsClock.string(from: lastSavedAt)
    }

    /// Retourne true si l'URL est non vide et parseable.
    var isConfigured: Bool {
        resolvedBaseURL() != nil
    }

    func update(baseURL: String, apiKey rawKey: String) {
        self.baseURL = Self.normalizeURL(baseURL)
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

    nonisolated static func normalizeURL(_ rawValue: String) -> String {
        var value = rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
        while value.hasSuffix("/") { value.removeLast() }
        return value
    }

    // MARK: - Keychain

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
    static let aperantSettingsClock: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.dateStyle = .short
        f.timeStyle = .short
        return f
    }()
}

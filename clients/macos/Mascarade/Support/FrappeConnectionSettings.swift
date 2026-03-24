//
//  FrappeConnectionSettings.swift
//  Mascarade
//
//  Réglages de connexion pour l'instance Frappe.
//  URL stockée dans UserDefaults.
//  API Key + API Secret stockés séparément dans le Keychain.
//  Auth header : "Authorization: token <api_key>:<api_secret>"
//

import Combine
import Foundation
import Security

@MainActor
final class FrappeConnectionSettings: ObservableObject {
    private enum Keys {
        static let baseURL        = "frappe.base-url"
        static let savedAt        = "frappe.saved-at"
        static let keychainApiKey = "frappe-api-key"
        static let keychainApiSecret = "frappe-api-secret"
        static let keychainService = Bundle.main.bundleIdentifier ?? "fr.lelectronrare.mascarade"
    }

    @Published var baseURL: String
    @Published private(set) var apiKeyIsSet: Bool
    @Published private(set) var lastSavedAt: Date?

    private let defaults: UserDefaults
    private(set) var apiKey: String = ""
    private(set) var apiSecret: String = ""

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        self.baseURL = defaults.string(forKey: Keys.baseURL) ?? "https://frappe.saillant.cc"
        self.lastSavedAt = defaults.object(forKey: Keys.savedAt) as? Date
        let storedKey    = Self.readKeychain(account: Keys.keychainApiKey)
        let storedSecret = Self.readKeychain(account: Keys.keychainApiSecret)
        self.apiKey    = storedKey    ?? ""
        self.apiSecret = storedSecret ?? ""
        self.apiKeyIsSet = (storedKey?.isEmpty == false) && (storedSecret?.isEmpty == false)
    }

    var normalizedBaseURL: String {
        Self.normalizeURL(baseURL)
    }

    var lastSavedAtLabel: String {
        guard let lastSavedAt else { return "jamais" }
        return DateFormatter.frappeSettingsClock.string(from: lastSavedAt)
    }

    /// Retourne true si l'URL est non vide et parseable.
    var isConfigured: Bool {
        resolvedBaseURL() != nil
    }

    /// Token header Frappe : "token key:secret"
    var authorizationHeader: String? {
        guard !apiKey.isEmpty, !apiSecret.isEmpty else { return nil }
        return "token \(apiKey):\(apiSecret)"
    }

    func update(baseURL: String, apiKey rawKey: String, apiSecret rawSecret: String) {
        self.baseURL   = Self.normalizeURL(baseURL)
        self.lastSavedAt = Date()

        defaults.set(self.baseURL,   forKey: Keys.baseURL)
        defaults.set(self.lastSavedAt, forKey: Keys.savedAt)

        let trimmedKey    = rawKey.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedSecret = rawSecret.trimmingCharacters(in: .whitespacesAndNewlines)

        if trimmedKey.isEmpty {
            Self.deleteKeychain(account: Keys.keychainApiKey)
            self.apiKey = ""
        } else {
            Self.writeKeychain(trimmedKey, account: Keys.keychainApiKey)
            self.apiKey = trimmedKey
        }

        if trimmedSecret.isEmpty {
            Self.deleteKeychain(account: Keys.keychainApiSecret)
            self.apiSecret = ""
        } else {
            Self.writeKeychain(trimmedSecret, account: Keys.keychainApiSecret)
            self.apiSecret = trimmedSecret
        }

        self.apiKeyIsSet = !trimmedKey.isEmpty && !trimmedSecret.isEmpty
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

    private static func writeKeychain(_ value: String, account: String) {
        guard let data = value.data(using: .utf8) else { return }
        deleteKeychain(account: account)
        let query: [String: Any] = [
            kSecClass as String:            kSecClassGenericPassword,
            kSecAttrService as String:      Keys.keychainService,
            kSecAttrAccount as String:      account,
            kSecValueData as String:        data,
            kSecAttrAccessible as String:   kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        ]
        SecItemAdd(query as CFDictionary, nil)
    }

    private static func readKeychain(account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String:        kSecClassGenericPassword,
            kSecAttrService as String:  Keys.keychainService,
            kSecAttrAccount as String:  account,
            kSecReturnData as String:   true,
            kSecMatchLimit as String:   kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    @discardableResult
    private static func deleteKeychain(account: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String:        kSecClassGenericPassword,
            kSecAttrService as String:  Keys.keychainService,
            kSecAttrAccount as String:  account,
        ]
        return SecItemDelete(query as CFDictionary) == errSecSuccess
    }
}

private extension DateFormatter {
    static let frappeSettingsClock: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.dateStyle = .short
        f.timeStyle = .short
        return f
    }()
}

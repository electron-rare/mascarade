//
//  FrappeRealtimeService.swift
//  Mascarade
//
//  Connexion Socket.io au serveur Frappe pour recevoir les mises à jour
//  en temps réel sur le DocType "Task".
//
//  Protocole Frappe Socket.io :
//  1. Connexion au namespace /<site_name> avec Authorization header (token key:secret)
//  2. Émission de "doctype_subscribe" avec "Task" → rejoint la room "doctype:Task"
//  3. Écoute de "doc_update" → payload { doctype, name }
//  4. Sur réception : refresh forcé du FrappeViewModel
//

import Combine
import Foundation
import SocketIO
import SwiftUI

@MainActor
final class FrappeRealtimeService: ObservableObject {

    @Published private(set) var isConnected = false
    @Published private(set) var lastEventAt: Date?

    private var manager: SocketManager?
    private var socket: SocketIOClient?

    /// Callback déclenché à chaque événement doc_update sur Task
    var onTaskUpdate: (() -> Void)?

    // MARK: - Connect

    func connect(settings: FrappeConnectionSettings) {
        disconnect()

        guard let baseURL = settings.resolvedBaseURL(),
              let authHeader = settings.authorizationHeader else {
            return
        }

        // Le namespace Frappe = nom du site (ex: tower.saillant.cc)
        let siteName = baseURL.host ?? ""

        // Socket.io v3 — on passe le header Authorization via extraHeaders
        let config: SocketIOClientConfiguration = [
            .log(false),
            .compress,
            .reconnects(true),
            .reconnectWait(5),
            .reconnectAttempts(10),
            .extraHeaders(["Authorization": authHeader]),
            .connectParams([:]),
            .secure(baseURL.scheme == "https"),
        ]

        // Le manager pointe sur la racine, le socket sur le namespace du site
        manager = SocketManager(socketURL: baseURL, config: config)
        socket = manager?.socket(forNamespace: "/\(siteName)")

        guard let socket else { return }

        socket.on(clientEvent: .connect) { [weak self] _, _ in
            Task { @MainActor [weak self] in
                self?.isConnected = true
                // S'abonner aux updates du DocType Task
                socket.emit("doctype_subscribe", "Task")
            }
        }

        socket.on(clientEvent: .disconnect) { [weak self] _, _ in
            Task { @MainActor [weak self] in
                self?.isConnected = false
            }
        }

        socket.on(clientEvent: .error) { data, _ in
            if let err = data.first {
                print("[FrappeRealtime] Erreur Socket.io:", err)
            }
        }

        // Frappe émet "doc_update" avec { doctype, name } lors de toute modification
        socket.on("doc_update") { [weak self] data, _ in
            Task { @MainActor [weak self] in
                guard let self else { return }
                // Vérifier que c'est bien un update de Task
                if let payload = data.first as? [String: Any],
                   let doctype = payload["doctype"] as? String,
                   doctype == "Task" {
                    self.lastEventAt = Date()
                    self.onTaskUpdate?()
                }
            }
        }

        // Aussi écouter list_update émis lors de création/suppression
        socket.on("list_update") { [weak self] data, _ in
            Task { @MainActor [weak self] in
                guard let self else { return }
                if let payload = data.first as? [String: Any],
                   let doctype = payload["doctype"] as? String,
                   doctype == "Task" {
                    self.lastEventAt = Date()
                    self.onTaskUpdate?()
                }
            }
        }

        socket.connect()
    }

    // MARK: - Disconnect

    func disconnect() {
        socket?.disconnect()
        socket = nil
        manager?.disconnect()
        manager = nil
        isConnected = false
    }
}

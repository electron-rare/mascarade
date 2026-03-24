//
//  AgentDetailSheet.swift
//  Mascarade
//
//  Agent detail + Agent Zero copilot interface.
//

import SwiftUI

struct AgentDetailSheet: View {
    let agent: AgentSummary
    @ObservedObject var settings: ConnectionSettings
    @Environment(\.dismiss) private var dismiss

    @State private var copilotPrompt = ""
    @State private var copilotLogs = ""
    @State private var copilotSeverity = "error"
    @State private var copilotResponse: CopilotResponse?
    @State private var copilotLoading = false
    @State private var copilotError: String?

    private let severities = ["debug", "info", "warning", "error", "critical"]
    private var isAgentZero: Bool { agent.name == "agent-zero" }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    agentInfoSection
                    if isAgentZero { copilotSection }
                }
                .padding(20)
            }
            .navigationTitle(agent.name)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Fermer") { dismiss() }
                }
            }
        }
        .frame(minWidth: 500, minHeight: isAgentZero ? 600 : 300)
    }

    // MARK: - Agent Info

    private var agentInfoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(agent.description)
                .font(.body)

            HStack(spacing: 8) {
                if let provider = agent.preferredProvider, !provider.isEmpty {
                    badge(provider, color: .orange)
                }
                if let model = agent.preferredModel, !model.isEmpty {
                    badge(model, color: .yellow)
                }
                if let strategy = agent.strategy, !strategy.isEmpty {
                    badge(strategy, color: .green)
                }
                if agent.builtin {
                    badge("builtin", color: .gray)
                }
            }
        }
    }

    // MARK: - Copilot

    private var copilotSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Divider()

            Text("Operator Copilot")
                .font(.headline)

            Text("Analyse d'incident — Agent Zero lit les logs et traces, propose la prochaine action manuelle.")
                .font(.caption)
                .foregroundColor(.secondary)

            // Prompt
            TextField("Decris l'incident ou la question...", text: $copilotPrompt, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(2...5)
                .padding(8)
                .background(Color(.controlBackgroundColor))
                .cornerRadius(8)

            // Logs
            VStack(alignment: .leading, spacing: 4) {
                Text("Logs (un par ligne, optionnel)")
                    .font(.caption)
                    .foregroundColor(.secondary)
                TextEditor(text: $copilotLogs)
                    .font(.system(.caption, design: .monospaced))
                    .frame(minHeight: 60, maxHeight: 120)
                    .padding(4)
                    .background(Color(.controlBackgroundColor))
                    .cornerRadius(6)
            }

            // Severity
            Picker("Severite", selection: $copilotSeverity) {
                ForEach(severities, id: \.self) { s in
                    Text(s).tag(s)
                }
            }
            .pickerStyle(.segmented)

            // Send
            HStack {
                Button(action: sendCopilot) {
                    if copilotLoading {
                        ProgressView()
                            .scaleEffect(0.7)
                    } else {
                        Label("Analyser", systemImage: "wand.and.stars")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(copilotPrompt.trimmingCharacters(in: .whitespaces).isEmpty || copilotLoading)

                Spacer()

                if let error = copilotError {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .lineLimit(2)
                }
            }

            // Response
            if let resp = copilotResponse {
                VStack(alignment: .leading, spacing: 8) {
                    Divider()
                    Text("Analyse")
                        .font(.headline)

                    Text(resp.content)
                        .font(.system(.body, design: .rounded))
                        .textSelection(.enabled)
                        .padding(10)
                        .background(Color(.controlBackgroundColor))
                        .cornerRadius(8)

                    HStack(spacing: 12) {
                        Text(resp.model)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Text(resp.provider)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        if let ctx = resp.operatorContext {
                            if let logs = ctx.logsCount, logs > 0 {
                                Text("\(logs) logs")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                }
            }
        }
    }

    // MARK: - Actions

    private func sendCopilot() {
        guard let baseURL = settings.resolvedBaseURL() else {
            copilotError = "URL non configuree"
            return
        }

        copilotLoading = true
        copilotError = nil
        copilotResponse = nil

        let logs = copilotLogs
            .components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }

        let request = CopilotRequest(
            mode: "incident",
            prompt: copilotPrompt,
            logs: logs,
            traces: [],
            service: nil,
            severity: copilotSeverity,
            projectId: "mascarade-app"
        )

        Task {
            let client = MascaradeAPI(baseURL: baseURL, apiKey: settings.apiKey)
            do {
                let response = try await client.post(
                    "/v1/api/agents/agent-zero/copilot",
                    body: request,
                    as: CopilotResponse.self
                )
                copilotResponse = response
            } catch {
                copilotError = error.localizedDescription
            }
            copilotLoading = false
        }
    }

    // MARK: - Helpers

    private func badge(_ text: String, color: Color) -> some View {
        Text(text)
            .font(.caption2)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color.opacity(0.15))
            .foregroundColor(color)
            .cornerRadius(6)
    }
}

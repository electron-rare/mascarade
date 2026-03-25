//
//  MistralBatchView.swift
//  Mascarade
//
//  Submit and monitor Mistral Batch API jobs through Mascarade core.
//

import SwiftUI

struct MistralBatchView: View {
    @ObservedObject var settings: ConnectionSettings
    @State private var selectedPreset = "ane-priority-models"
    @State private var selectedModel = "mistral-large-latest"
    @State private var jobId: String?
    @State private var jobStatus: BatchJobResponse?
    @State private var results: [BatchResult] = []
    @State private var isSubmitting = false
    @State private var isPolling = false
    @State private var errorMessage: String?

    private let models = [
        "mistral-large-latest",
        "mistral-small-latest",
        "codestral-latest",
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                headerSection
                submitSection
                if jobId != nil { statusSection }
                if !results.isEmpty { resultsSection }
            }
            .padding(20)
        }
        .navigationTitle("Mistral Batch")
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Batch Inference")
                .font(.title2.bold())
            Text("Soumet un lot de requetes a l'API Mistral Batch via Mascarade. Pas de modele en RAM.")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    // MARK: - Submit

    private var submitSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Preset")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Picker("Preset", selection: $selectedPreset) {
                        Text("ANE Priority Models").tag("ane-priority-models")
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: 250)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text("Modele")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Picker("Model", selection: $selectedModel) {
                        ForEach(models, id: \.self) { m in
                            Text(m).tag(m)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(maxWidth: 250)
                }
            }

            HStack {
                Button(action: submitPreset) {
                    if isSubmitting {
                        ProgressView().scaleEffect(0.7)
                    } else {
                        Label("Lancer le batch", systemImage: "play.circle")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isSubmitting || isPolling)

                if let jobId {
                    Button(action: pollStatus) {
                        if isPolling {
                            ProgressView().scaleEffect(0.7)
                        } else {
                            Label("Rafraichir", systemImage: "arrow.clockwise")
                        }
                    }
                    .buttonStyle(.bordered)
                    .disabled(isPolling)

                    Text(jobId)
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(.secondary)
                        .textSelection(.enabled)
                }

                Spacer()

                if let error = errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .lineLimit(2)
                }
            }
        }
    }

    // MARK: - Status

    private var statusSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider()
            Text("Status")
                .font(.headline)

            if let job = jobStatus {
                HStack(spacing: 16) {
                    statusBadge(job.status)
                    Text("\(job.succeededRequests ?? 0)/\(job.totalRequests) reussis")
                        .font(.body.monospacedDigit())
                    if let failed = job.failedRequests, failed > 0 {
                        Text("\(failed) echoues")
                            .font(.body.monospacedDigit())
                            .foregroundColor(.red)
                    }
                }

                if job.status == "SUCCESS" && results.isEmpty {
                    Button("Telecharger les resultats") { fetchResults() }
                        .buttonStyle(.borderedProminent)
                }
            }
        }
    }

    // MARK: - Results

    private var resultsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Divider()
            Text("Resultats")
                .font(.headline)

            ForEach(results) { result in
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(result.customId)
                            .font(.system(.subheadline, design: .monospaced).bold())
                        Spacer()
                        if let usage = result.usage {
                            Text("\(usage.promptTokens ?? 0) in / \(usage.completionTokens ?? 0) out")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                    }

                    Text(result.content)
                        .font(.system(.caption, design: .rounded))
                        .lineLimit(6)
                        .textSelection(.enabled)
                        .padding(8)
                        .background(Color(.controlBackgroundColor))
                        .cornerRadius(6)
                }
            }
        }
    }

    // MARK: - Actions

    private func submitPreset() {
        guard let baseURL = settings.resolvedBaseURL() else {
            errorMessage = "URL non configuree"
            return
        }

        isSubmitting = true
        errorMessage = nil
        results = []
        jobStatus = nil

        Task {
            let client = MascaradeAPI(baseURL: baseURL, apiKey: settings.apiKey)
            do {
                let body = BatchSubmitRequest(model: selectedModel)
                let response = try await client.post(
                    "/v1/api/mistral-batch/presets/\(selectedPreset)?model=\(selectedModel)",
                    body: body,
                    as: BatchJobResponse.self
                )
                jobId = response.jobId
                jobStatus = response
            } catch {
                errorMessage = error.localizedDescription
            }
            isSubmitting = false
        }
    }

    private func pollStatus() {
        guard let baseURL = settings.resolvedBaseURL(), let jobId else { return }

        isPolling = true
        errorMessage = nil

        Task {
            let client = MascaradeAPI(baseURL: baseURL, apiKey: settings.apiKey)
            do {
                let response = try await client.get(
                    "/v1/api/mistral-batch/jobs/\(jobId)",
                    as: BatchJobResponse.self
                )
                jobStatus = response
                if response.status == "SUCCESS" { fetchResults() }
            } catch {
                errorMessage = error.localizedDescription
            }
            isPolling = false
        }
    }

    private func fetchResults() {
        guard let baseURL = settings.resolvedBaseURL(), let jobId else { return }

        Task {
            let client = MascaradeAPI(baseURL: baseURL, apiKey: settings.apiKey)
            do {
                let response = try await client.get(
                    "/v1/api/mistral-batch/jobs/\(jobId)/results",
                    as: BatchResultsResponse.self
                )
                results = response.results
            } catch {
                errorMessage = "Resultats: \(error.localizedDescription)"
            }
        }
    }

    // MARK: - Helpers

    private func statusBadge(_ status: String) -> some View {
        let (color, icon): (Color, String) = switch status {
        case "SUCCESS": (.green, "checkmark.circle.fill")
        case "RUNNING": (.blue, "arrow.triangle.2.circlepath")
        case "QUEUED": (.orange, "clock.fill")
        case "FAILED": (.red, "xmark.circle.fill")
        default: (.gray, "questionmark.circle")
        }

        return HStack(spacing: 4) {
            Image(systemName: icon)
            Text(status)
        }
        .font(.caption.bold())
        .foregroundColor(color)
    }
}

//
//  SettingsView.swift
//  Mascarade
//

import SwiftUI

struct SettingsView: View {
    @ObservedObject var settings: ConnectionSettings
    @ObservedObject var viewModel: CockpitViewModel
    @ObservedObject var apeSettings: AperantConnectionSettings
    @ObservedObject var frappeSettings: FrappeConnectionSettings
    @State private var draftBaseURL = ""
    @State private var draftAPIKey = ""
    @State private var revealsApiKey = false

    private var metrics: [HeaderMetric] {
        [
            HeaderMetric(label: "Saved URL", value: settings.normalizedBaseURL.isEmpty ? "n/a" : settings.normalizedBaseURL, note: "cible active"),
            HeaderMetric(label: "API key", value: settings.apiKey.isEmpty ? "open" : "configured", note: "masque"),
            HeaderMetric(label: "Refresh", value: viewModel.lastRefreshLabel, note: "derniere sync"),
        ]
    }

    private var tarotLine: String {
        if settings.normalizedBaseURL.isEmpty {
            return "La prise n'a pas encore trouve son mur."
        }

        if settings.apiKey.isEmpty {
            return "La facade est visible a mains nues."
        }

        return "La cle se cache dans la manche, la facade attend."
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                CollectionHeader(
                    eyebrow: "Rituel de connexion",
                    title: "Connexion",
                    message: tarotLine,
                    metrics: metrics
                )

                SectionCard(title: "Le tarot du cable", eyebrow: "signal", tilt: -1.1, accent: MascaradeTheme.blue) {
                    ArtifactNote(text: tarotLine)
                    HStack(spacing: 8) {
                        CapsuleLabel(text: settings.normalizedBaseURL.isEmpty ? "adresse absente" : "adresse tenue", tone: MascaradeTheme.signal)
                        CapsuleLabel(text: settings.apiKey.isEmpty ? "visage nu" : "visage masque", tone: MascaradeTheme.amber)
                        CapsuleLabel(text: viewModel.apiIsHealthy ? "facade reveillee" : "facade froissee", tone: viewModel.apiIsHealthy ? MascaradeTheme.success : MascaradeTheme.error)
                    }
                }

                SectionCard(title: "La cible", eyebrow: "HTTP facade", tilt: 0.9) {
                    Text("L'app parle a la facade HTTP Mascarade sur le port 3100. En simulateur, 127.0.0.1 convient. Sur appareil physique, utilise plutot l'IP de la machine ou de la VM.")
                        .font(.system(.body, design: .rounded))
                        .foregroundStyle(MascaradeTheme.foreground)

                    VStack(alignment: .leading, spacing: 10) {
                        Text("Base URL")
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(MascaradeTheme.muted)
                        TextField("http://127.0.0.1:3100", text: $draftBaseURL)
                            .mascaradeTextInput()
                            .padding(14)
                            .background(MascaradeTheme.panel)
                            .overlay(
                                RoundedRectangle(cornerRadius: 16, style: .continuous)
                                    .stroke(MascaradeTheme.rule, lineWidth: 1)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        Toggle("Afficher la cle API", isOn: $revealsApiKey)
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(MascaradeTheme.muted)

                        if revealsApiKey {
                            TextField("Bearer token optionnel", text: $draftAPIKey)
                                .mascaradeTextInput()
                                .padding(14)
                                .background(MascaradeTheme.panel)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                                        .stroke(MascaradeTheme.rule, lineWidth: 1)
                                )
                                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                        } else {
                            SecureField("Bearer token optionnel", text: $draftAPIKey)
                                .mascaradeTextInput()
                                .padding(14)
                                .background(MascaradeTheme.panel)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                                        .stroke(MascaradeTheme.rule, lineWidth: 1)
                                )
                                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                        }
                    }

                    HStack(spacing: 12) {
                        Button("Enregistrer") {
                            save()
                        }
                        .buttonStyle(PrimaryButtonStyle())

                        Button("Enregistrer et recharger") {
                            save()
                            Task {
                                await viewModel.refresh(using: settings)
                            }
                        }
                        .buttonStyle(SecondaryButtonStyle())
                    }
                }

                SectionCard(title: "L'etat", eyebrow: "snapshot", tilt: -0.8) {
                    MetricRow(label: "Saved URL", value: settings.normalizedBaseURL.isEmpty ? "n/a" : settings.normalizedBaseURL)
                    MetricRow(label: "API key", value: settings.apiKey.isEmpty ? "not set" : "configured")
                    MetricRow(label: "Last save", value: settings.lastSavedAtLabel)
                    MetricRow(label: "Last refresh", value: viewModel.lastRefreshLabel)
                }

                SectionCard(title: "Les presets", eyebrow: "fast switch", tilt: 1.2) {
                    Button("Use simulator localhost") {
                        draftBaseURL = "http://127.0.0.1:3100"
                    }
                    .buttonStyle(SecondaryButtonStyle())

                    Button("Use VM host example") {
                        draftBaseURL = "http://192.168.0.119:3100"
                    }
                    .buttonStyle(SecondaryButtonStyle())
                }

                AperantSettingsSection(apeSettings: apeSettings)

                FrappeSettingsSection(frappeSettings: frappeSettings)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 24)
        }
        .navigationTitle("Rituel")
        .onAppear {
            syncDrafts()
        }
    }

    private func save() {
        settings.update(baseURL: draftBaseURL, apiKey: draftAPIKey)
        syncDrafts()
    }

    private func syncDrafts() {
        draftBaseURL = settings.normalizedBaseURL
        draftAPIKey = settings.apiKey
    }
}

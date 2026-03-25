//
//  AgentsView.swift
//  Mascarade
//

import SwiftUI

struct AgentsView: View {
    @ObservedObject var viewModel: CockpitViewModel
    @ObservedObject var settings: ConnectionSettings
    @State private var searchText = ""
    @State private var focusedAgentID: String?
    @State private var scatterSeed = 0
    @State private var detailAgent: AgentSummary?

    private var filteredAgents: [AgentSummary] {
        guard !searchText.isEmpty else {
            return viewModel.agents
        }

        let needle = searchText.localizedLowercase
        return viewModel.agents.filter { agent in
            agent.name.localizedLowercase.contains(needle)
                || agent.description.localizedLowercase.contains(needle)
                || (agent.preferredProvider?.localizedLowercase.contains(needle) ?? false)
                || (agent.preferredModel?.localizedLowercase.contains(needle) ?? false)
        }
    }

    private var focusedAgent: AgentSummary? {
        guard let focusedAgentID else {
            return filteredAgents.first
        }

        return filteredAgents.first(where: { $0.id == focusedAgentID }) ?? filteredAgents.first
    }

    private var metrics: [HeaderMetric] {
        [
            HeaderMetric(label: "Visible", value: "\(filteredAgents.count)", note: "dans la pile"),
            HeaderMetric(label: "Builtin", value: "\(viewModel.agents.filter(\.builtin).count)", note: "interieurs"),
            HeaderMetric(label: "Providers", value: "\(Set(viewModel.agents.compactMap(\.preferredProvider)).count)", note: "masques"),
        ]
    }

    private var filteredAgentSignature: String {
        filteredAgents.map(\.id).joined(separator: "|")
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                CollectionHeader(
                    eyebrow: "Registry en vrac",
                    title: "Agents",
                    message: focusedAgent == nil ? "La pile attend son premier visage." : "\(focusedAgent?.name ?? "Un agent") prend la lumiere pendant que le reste penche autour.",
                    metrics: metrics
                )

                HStack(spacing: 12) {
                    Button("Secouer le registre") {
                        withAnimation(.spring(response: 0.52, dampingFraction: 0.82)) {
                            scatterSeed += 1
                            focusedAgentID = filteredAgents.randomElement()?.id
                        }
                    }
                    .buttonStyle(PrimaryButtonStyle())

                    if let focusedAgent {
                        CapsuleLabel(text: focusedAgent.name, tone: MascaradeTheme.blue)
                    }
                }

                if filteredAgents.isEmpty {
                    SectionCard(title: "Pas de visage", eyebrow: "registry", tilt: 0.6) {
                        EmptyLane(message: searchText.isEmpty ? "Aucun agent charge." : "Aucun agent ne correspond a la recherche.")
                    }
                } else {
                    ForEach(filteredAgents) { agent in
                        let selected = agent.id == focusedAgent?.id

                        Button {
                            withAnimation(.spring(response: 0.48, dampingFraction: 0.84)) {
                                focusedAgentID = selected ? nil : agent.id
                            }
                        } label: {
                            SectionCard(
                                title: agent.name,
                                eyebrow: agent.preferredProvider ?? "registry",
                                tilt: deterministicAngle(for: agent.id, seed: scatterSeed, amplitude: 2.4),
                                accent: selected ? MascaradeTheme.blue : MascaradeTheme.rule
                            ) {
                                Text(agent.description)
                                    .font(.system(.body, design: .rounded))
                                    .foregroundStyle(MascaradeTheme.foreground)
                                    .multilineTextAlignment(.leading)

                                HStack(spacing: 8) {
                                    if let provider = agent.preferredProvider, !provider.isEmpty {
                                        CapsuleLabel(text: provider, tone: MascaradeTheme.signal)
                                    }
                                    if let model = agent.preferredModel, !model.isEmpty {
                                        CapsuleLabel(text: model, tone: MascaradeTheme.amber)
                                    }
                                    if let role = agent.preferredRole, !role.isEmpty {
                                        CapsuleLabel(text: role, tone: MascaradeTheme.panelBorder)
                                    }
                                    if let strategy = agent.strategy, !strategy.isEmpty {
                                        CapsuleLabel(text: strategy, tone: MascaradeTheme.success)
                                    }
                                    if agent.builtin {
                                        CapsuleLabel(text: "builtin", tone: MascaradeTheme.foreground)
                                    }
                                }

                                if selected {
                                    ArtifactNote(
                                        text: "\(agent.name) traverse le rideau avec \(agent.preferredModel ?? "un modele anonyme") et laisse \(agent.strategy ?? "une strategie muette") sur la table."
                                    )
                                    .transition(.collageShard)
                                }
                            }
                            .scaleEffect(selected ? 1.015 : 1)
                        }
                        .buttonStyle(.plain)
                        .onTapGesture(count: 2) {
                            detailAgent = agent
                        }
                        .contextMenu {
                            Button("Ouvrir le detail") { detailAgent = agent }
                            if agent.name == "agent-zero" {
                                Button("Copilot") { detailAgent = agent }
                            }
                        }
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 24)
        }
        .navigationTitle("Agents")
        .searchable(text: $searchText, prompt: "agent-zero, claude, orchestration...")
        .sheet(item: $detailAgent) { agent in
            AgentDetailSheet(agent: agent, settings: settings)
        }
        .onAppear {
            focusedAgentID = focusedAgentID ?? filteredAgents.first?.id
        }
        .onChange(of: filteredAgentSignature) { _, _ in
            if focusedAgentID == nil || !filteredAgents.contains(where: { $0.id == focusedAgentID }) {
                focusedAgentID = filteredAgents.first?.id
            }
        }
    }
}

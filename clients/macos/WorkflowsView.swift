//
//  WorkflowsView.swift
//  Mascarade
//

import SwiftUI

struct WorkflowsView: View {
    @ObservedObject var viewModel: CockpitViewModel
    @State private var searchText = ""
    @State private var focusedWorkflowID: String?
    @State private var scatterSeed = 0

    private var filteredWorkflows: [WorkflowSummary] {
        guard !searchText.isEmpty else {
            return viewModel.workflows
        }

        let needle = searchText.localizedLowercase
        return viewModel.workflows.filter { workflow in
            workflow.title.localizedLowercase.contains(needle)
                || workflow.category.localizedLowercase.contains(needle)
                || workflow.tags.contains(where: { $0.localizedLowercase.contains(needle) })
        }
    }

    private var focusedWorkflow: WorkflowSummary? {
        guard let focusedWorkflowID else {
            return filteredWorkflows.first
        }

        return filteredWorkflows.first(where: { $0.id == focusedWorkflowID }) ?? filteredWorkflows.first
    }

    private var metrics: [HeaderMetric] {
        [
            HeaderMetric(label: "Visible", value: "\(filteredWorkflows.count)", note: "dans la pile"),
            HeaderMetric(
                label: "Success",
                value: "\(filteredWorkflows.filter { $0.latestRun?.status == "success" }.count)",
                note: "dernier run ok"
            ),
            HeaderMetric(
                label: "Failed",
                value: "\(filteredWorkflows.filter { $0.latestRun?.status == "failed" }.count)",
                note: "dernier run ko"
            ),
        ]
    }

    var body: some View {
        ScrollView {
            workflowContent
        }
        .navigationTitle("Lanes")
        .searchable(text: $searchText, prompt: "release, firmware, evidence...")
        .onAppear {
            focusedWorkflowID = focusedWorkflowID ?? filteredWorkflows.first?.id
        }
        .onChange(of: filteredWorkflowSignature) { _, _ in
            if focusedWorkflowID == nil || !filteredWorkflows.contains(where: { $0.id == focusedWorkflowID }) {
                focusedWorkflowID = filteredWorkflows.first?.id
            }
        }
    }

    private var filteredWorkflowSignature: String {
        filteredWorkflows.map(\.id).joined(separator: "|")
    }

    private var workflowContent: some View {
        VStack(alignment: .leading, spacing: 20) {
            CollectionHeader(
                eyebrow: "Kill_LIFE collage",
                title: "Workflows",
                message: focusedWorkflow == nil ? "Les lanes attendent le premier geste." : "\(focusedWorkflow?.title ?? "Une lane") vient de se detacher du paquet.",
                metrics: metrics
            )

            HStack(spacing: 12) {
                Button("Battre les cartes") {
                    withAnimation(.spring(response: 0.52, dampingFraction: 0.82)) {
                        scatterSeed += 1
                        focusedWorkflowID = filteredWorkflows.randomElement()?.id
                    }
                }
                .buttonStyle(PrimaryButtonStyle())

                if let focusedWorkflow {
                    CapsuleLabel(text: focusedWorkflow.category, tone: MascaradeTheme.signal)
                }
            }

            workflowList
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 24)
    }

    @ViewBuilder
    private var workflowList: some View {
        if filteredWorkflows.isEmpty {
            SectionCard(title: "Pas de lane", eyebrow: "kill_life", tilt: -0.7) {
                EmptyLane(message: searchText.isEmpty ? "Aucun workflow recupere depuis /api/killlife/workflows." : "Aucun workflow ne correspond a la recherche.")
            }
        } else {
            ForEach(filteredWorkflows) { workflow in
                workflowButton(for: workflow)
            }
        }
    }

    private func workflowButton(for workflow: WorkflowSummary) -> some View {
        let selected = workflow.id == focusedWorkflow?.id

        return Button {
            withAnimation(.spring(response: 0.48, dampingFraction: 0.84)) {
                focusedWorkflowID = selected ? nil : workflow.id
            }
        } label: {
            WorkflowDeckCard(
                workflow: workflow,
                selected: selected,
                tilt: deterministicAngle(for: workflow.id, seed: scatterSeed, amplitude: 2.8)
            )
        }
        .buttonStyle(.plain)
    }
}

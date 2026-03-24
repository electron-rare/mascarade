//
//  AperantView.swift
//  Mascarade
//
//  Vue principale de l'onglet Aperant.
//  Trois sections : liste des specs, détail/plan, formulaire "Confier à Aperant".
//

import SwiftUI

// MARK: - Root view

struct AperantView: View {
    @ObservedObject var apeSettings: AperantConnectionSettings
    @StateObject private var viewModel = AperantViewModel()

    @State private var selectedSpecID: String?
    @State private var showCreateSheet = false

    private var metrics: [HeaderMetric] {
        [
            HeaderMetric(
                label: "Specs",
                value: "\(viewModel.specs.count)",
                note: "dans la file"
            ),
            HeaderMetric(
                label: "Bridge",
                value: viewModel.isHealthy ? "up" : "down",
                note: "aperant-bridge"
            ),
            HeaderMetric(
                label: "Sync",
                value: viewModel.lastRefreshLabel,
                note: "dernier refresh"
            ),
        ]
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {

                CollectionHeader(
                    eyebrow: "Pilote de specs",
                    title: "Aperant",
                    message: headerMessage,
                    metrics: metrics
                )

                // Banner d'erreur
                if let banner = viewModel.bannerMessage {
                    SectionCard(title: "Signal brouillé", eyebrow: "bridge", tilt: -0.8, accent: MascaradeTheme.error) {
                        ArtifactNote(text: banner)
                    }
                }

                // Statut de la connexion
                if !apeSettings.isConfigured {
                    SectionCard(title: "Bridge non configuré", eyebrow: "configuration", tilt: 1.2, accent: MascaradeTheme.amber) {
                        ArtifactNote(text: "Configure l'URL du bridge Aperant dans l'onglet Rituel avant de continuer.")
                    }
                } else {
                    // Barre d'actions
                    HStack(spacing: 12) {
                        Button("Nouveau spec") {
                            showCreateSheet = true
                        }
                        .buttonStyle(PrimaryButtonStyle())

                        Button {
                            Task { await viewModel.refresh(using: apeSettings, force: true) }
                        } label: {
                            Label(
                                viewModel.isRefreshing ? "Rafraîchissement…" : "Rafraîchir",
                                systemImage: "arrow.clockwise"
                            )
                        }
                        .buttonStyle(SecondaryButtonStyle())
                        .disabled(viewModel.isRefreshing)

                        if viewModel.isHealthy {
                            CapsuleLabel(text: "bridge up", tone: MascaradeTheme.success)
                        } else {
                            CapsuleLabel(text: "bridge down", tone: MascaradeTheme.error)
                        }
                    }

                    // Liste des specs
                    specsSection
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 16)
        }
        .navigationTitle("Aperant")
        .searchable(text: .constant(""))
        .task {
            guard apeSettings.isConfigured else { return }
            await viewModel.refresh(using: apeSettings)
        }
        .sheet(isPresented: $showCreateSheet) {
            AperantCreateSheet(apeSettings: apeSettings, viewModel: viewModel)
        }
        .sheet(item: Binding(
            get: { viewModel.selectedSpec },
            set: { if $0 == nil { viewModel.clearSelectedSpec() } }
        )) { spec in
            AperantSpecDetailSheet(
                spec: spec,
                apeSettings: apeSettings,
                viewModel: viewModel
            )
        }
    }

    // MARK: - Specs list

    @ViewBuilder
    private var specsSection: some View {
        if viewModel.specs.isEmpty && !viewModel.isRefreshing {
            SectionCard(title: "File vide", eyebrow: "specs", tilt: 0.5) {
                EmptyLane(message: "Aucun spec dans la file. Crée-en un via 'Nouveau spec'.")
            }
        } else {
            SectionCard(title: "Specs en file", eyebrow: "aperant", tilt: -0.6) {
                LazyVStack(spacing: 8) {
                    ForEach(viewModel.specs) { spec in
                        AperantSpecRow(spec: spec) {
                            Task {
                                await viewModel.loadSpec(spec.id, using: apeSettings)
                            }
                        } onDelete: {
                            Task {
                                await viewModel.deleteSpec(spec.id, using: apeSettings)
                            }
                        }
                    }
                }
            }
        }
    }

    // MARK: - Header message

    private var headerMessage: String {
        guard apeSettings.isConfigured else {
            return "Le bridge attend son adresse pour prendre le masque."
        }
        if viewModel.isRefreshing {
            return "Lecture de la file…"
        }
        if viewModel.specs.isEmpty {
            return "La file est vide. Chaque spec confié devient un acte de délégation."
        }
        let running = viewModel.specs.filter { $0.specStatus == .running }.count
        if running > 0 {
            return "\(running) spec\(running > 1 ? "s" : "") en cours de traitement par Aperant."
        }
        return "\(viewModel.specs.count) spec\(viewModel.specs.count > 1 ? "s" : "") dans la file."
    }
}

// MARK: - Spec row

private struct AperantSpecRow: View {
    let spec: AperantSpecSummary
    let onTap: () -> Void
    let onDelete: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(alignment: .center, spacing: 12) {
                Image(systemName: spec.specStatus.systemImage)
                    .font(.system(size: 16, weight: .medium))
                    .foregroundStyle(statusColor)
                    .frame(width: 22)

                VStack(alignment: .leading, spacing: 3) {
                    Text(spec.title)
                        .font(.system(.subheadline, design: .rounded).weight(.medium))
                        .foregroundStyle(MascaradeTheme.foreground)
                        .lineLimit(1)

                    HStack(spacing: 6) {
                        if let project = spec.project, !project.isEmpty {
                            CapsuleLabel(text: project, tone: MascaradeTheme.blue)
                        }
                        CapsuleLabel(text: spec.specStatus.label, tone: statusColor)
                    }
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(MascaradeTheme.muted)
            }
            .padding(.vertical, 10)
            .padding(.horizontal, 12)
            .background(MascaradeTheme.card, in: RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(MascaradeTheme.rule, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .contextMenu {
            Button(role: .destructive) {
                onDelete()
            } label: {
                Label("Supprimer", systemImage: "trash")
            }
        }
        .swipeActions(edge: .trailing) {
            Button(role: .destructive, action: onDelete) {
                Label("Supprimer", systemImage: "trash")
            }
        }
    }

    private var statusColor: Color {
        switch spec.specStatus {
        case .pending: MascaradeTheme.amber
        case .running: MascaradeTheme.blue
        case .done:    MascaradeTheme.success
        case .failed:  MascaradeTheme.error
        case .unknown: MascaradeTheme.muted
        }
    }
}

// MARK: - Spec detail sheet

struct AperantSpecDetailSheet: View {
    let spec: AperantSpecDetail
    @ObservedObject var apeSettings: AperantConnectionSettings
    @ObservedObject var viewModel: AperantViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {

                    // Status + metadata
                    HStack(spacing: 8) {
                        Image(systemName: spec.specStatus.systemImage)
                            .foregroundStyle(statusColor)
                        Text(spec.specStatus.label)
                            .font(.system(.subheadline, design: .rounded).weight(.medium))
                            .foregroundStyle(statusColor)
                        if let project = spec.project, !project.isEmpty {
                            CapsuleLabel(text: project, tone: MascaradeTheme.blue)
                        }
                        Spacer()
                        Text(spec.updatedAt.prefix(10))
                            .font(.caption.monospaced())
                            .foregroundStyle(MascaradeTheme.muted)
                    }
                    .padding(.horizontal, 20)

                    // Contenu spec
                    SectionCard(title: "Spec", eyebrow: spec.id, tilt: -0.5) {
                        Text(spec.content.isEmpty ? "(vide)" : spec.content)
                            .font(.system(.body, design: .monospaced))
                            .foregroundStyle(MascaradeTheme.foreground)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .textSelection(.enabled)
                    }

                    // Plan (si disponible)
                    if let plan = spec.plan {
                        SectionCard(title: "Plan d'implémentation", eyebrow: "phases", tilt: 0.7, accent: MascaradeTheme.blue) {
                            AperantPlanView(plan: plan)
                        }
                    } else {
                        SectionCard(title: "Plan en attente", eyebrow: "phases", tilt: 0.7) {
                            ArtifactNote(text: "Aperant n'a pas encore généré le plan pour ce spec.")
                        }
                    }
                }
                .padding(.vertical, 16)
            }
            .navigationTitle(spec.title)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Fermer") { dismiss() }
                }
                ToolbarItem(placement: .destructiveAction) {
                    Button(role: .destructive) {
                        Task {
                            await viewModel.deleteSpec(spec.id, using: apeSettings)
                            dismiss()
                        }
                    } label: {
                        Label("Supprimer", systemImage: "trash")
                    }
                }
            }
        }
    }

    private var statusColor: Color {
        switch spec.specStatus {
        case .pending: MascaradeTheme.amber
        case .running: MascaradeTheme.blue
        case .done:    MascaradeTheme.success
        case .failed:  MascaradeTheme.error
        case .unknown: MascaradeTheme.muted
        }
    }
}

// MARK: - Plan view

private struct AperantPlanView: View {
    let plan: AperantPlan

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let summary = plan.summary, !summary.isEmpty {
                ArtifactNote(text: summary)
            }
            if let complexity = plan.estimatedComplexity {
                CapsuleLabel(text: "Complexité: \(complexity)", tone: MascaradeTheme.amber)
            }
            if let phases = plan.phases, !phases.isEmpty {
                ForEach(phases) { phase in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(phase.name)
                            .font(.system(.subheadline, design: .rounded).weight(.semibold))
                            .foregroundStyle(MascaradeTheme.foreground)
                        if let desc = phase.description, !desc.isEmpty {
                            Text(desc)
                                .font(.system(.caption, design: .rounded))
                                .foregroundStyle(MascaradeTheme.muted)
                        }
                        if let tasks = phase.tasks, !tasks.isEmpty {
                            ForEach(tasks) { task in
                                HStack(alignment: .top, spacing: 6) {
                                    Image(systemName: task.status == "done" ? "checkmark.circle.fill" : "circle")
                                        .font(.caption)
                                        .foregroundStyle(task.status == "done" ? MascaradeTheme.success : MascaradeTheme.muted)
                                    Text(task.description)
                                        .font(.system(.caption, design: .rounded))
                                        .foregroundStyle(MascaradeTheme.foreground)
                                }
                            }
                        }
                    }
                    .padding(.vertical, 4)
                    Divider().overlay(MascaradeTheme.rule)
                }
            }
        }
    }
}

// MARK: - Create sheet

struct AperantCreateSheet: View {
    @ObservedObject var apeSettings: AperantConnectionSettings
    @ObservedObject var viewModel: AperantViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var title = ""
    @State private var content = ""
    @State private var project = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Titre") {
                    TextField("Ex: Refactoriser le module auth", text: $title)
                }
                Section("Projet (optionnel)") {
                    TextField("Ex: mascarade", text: $project)
                }
                Section("Contenu du spec") {
                    TextEditor(text: $content)
                        .font(.system(.body, design: .monospaced))
                        .frame(minHeight: 160)
                }
            }
            .navigationTitle("Nouveau spec Aperant")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Annuler") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Confier") {
                        guard !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
                        Task {
                            await viewModel.createSpec(
                                title: title.trimmingCharacters(in: .whitespacesAndNewlines),
                                content: content,
                                project: project.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : project.trimmingCharacters(in: .whitespacesAndNewlines),
                                vaultEntryId: nil,
                                vaultEntryTitle: nil,
                                using: apeSettings
                            )
                            dismiss()
                        }
                    }
                    .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || viewModel.isCreating)
                }
            }
        }
    }
}

// MARK: - "Confier à Aperant" button (used from VaultEntry context)

/// Bouton compact à placer dans un contexte vault entry.
struct ConfierAperantButton: View {
    let entry: VaultEntry
    @ObservedObject var apeSettings: AperantConnectionSettings
    @ObservedObject var viewModel: AperantViewModel
    @State private var showConfirmation = false
    @State private var didConfier = false

    var body: some View {
        Button {
            showConfirmation = true
        } label: {
            Label(didConfier ? "Confié" : "Confier à Aperant", systemImage: didConfier ? "checkmark.circle.fill" : "arrow.up.forward.circle")
        }
        .disabled(viewModel.isCreating || didConfier || !apeSettings.isConfigured)
        .confirmationDialog(
            "Confier «\(entry.safeTitle)» à Aperant ?",
            isPresented: $showConfirmation,
            titleVisibility: .visible
        ) {
            Button("Confier") {
                Task {
                    let result = await viewModel.createSpec(
                        title: entry.safeTitle,
                        content: entry.content ?? "",
                        project: entry.safeProject.isEmpty ? nil : entry.safeProject,
                        vaultEntryId: entry.objectID.uriRepresentation().absoluteString,
                        vaultEntryTitle: entry.safeTitle,
                        using: apeSettings
                    )
                    if result != nil { didConfier = true }
                }
            }
            Button("Annuler", role: .cancel) {}
        } message: {
            Text("Une spec Aperant sera créée avec le contenu de cette entrée.")
        }
    }
}

// MARK: - Frappe settings section (for SettingsView)

struct FrappeSettingsSection: View {
    @ObservedObject var frappeSettings: FrappeConnectionSettings
    @State private var draftURL = ""
    @State private var draftKey = ""
    @State private var draftSecret = ""
    @State private var revealsKey = false
    @State private var saved = false

    var body: some View {
        SectionCard(title: "Frappe / ERPNext", eyebrow: "frappe.saillant.cc", tilt: -0.7, accent: MascaradeTheme.signal) {
            Text("Kanban alimenté par les tâches Frappe. Auth : API Key + API Secret (token key:secret).")
                .font(.system(.body, design: .rounded))
                .foregroundStyle(MascaradeTheme.foreground)

            VStack(alignment: .leading, spacing: 10) {
                Text("URL Frappe")
                    .font(.system(.caption, design: .rounded).weight(.medium))
                    .foregroundStyle(MascaradeTheme.muted)
                TextField("https://frappe.saillant.cc", text: $draftURL)
                    .textFieldStyle(.roundedBorder)
                    .autocorrectionDisabled()
                    .onAppear { draftURL = frappeSettings.normalizedBaseURL }
            }

            VStack(alignment: .leading, spacing: 10) {
                Text("API Key")
                    .font(.system(.caption, design: .rounded).weight(.medium))
                    .foregroundStyle(MascaradeTheme.muted)
                HStack {
                    Group {
                        if revealsKey {
                            TextField("API Key", text: $draftKey)
                        } else {
                            SecureField("API Key", text: $draftKey)
                        }
                    }
                    .textFieldStyle(.roundedBorder)
                    .autocorrectionDisabled()
                    Button { revealsKey.toggle() } label: {
                        Image(systemName: revealsKey ? "eye.slash" : "eye")
                    }
                    .buttonStyle(.borderless)
                }
            }

            VStack(alignment: .leading, spacing: 10) {
                Text("API Secret")
                    .font(.system(.caption, design: .rounded).weight(.medium))
                    .foregroundStyle(MascaradeTheme.muted)
                Group {
                    if revealsKey {
                        TextField("API Secret", text: $draftSecret)
                    } else {
                        SecureField("API Secret", text: $draftSecret)
                    }
                }
                .textFieldStyle(.roundedBorder)
                .autocorrectionDisabled()
            }

            HStack(spacing: 12) {
                Button(saved ? "Sauvegardé ✓" : "Sauvegarder") {
                    frappeSettings.update(baseURL: draftURL, apiKey: draftKey, apiSecret: draftSecret)
                    withAnimation { saved = true }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                        withAnimation { saved = false }
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(saved)

                if frappeSettings.apiKeyIsSet {
                    CapsuleLabel(text: "token configuré", tone: MascaradeTheme.success)
                } else {
                    CapsuleLabel(text: "sans auth", tone: MascaradeTheme.muted)
                }
            }
        }
    }
}

// MARK: - Aperant settings section (for SettingsView)

struct AperantSettingsSection: View {
    @ObservedObject var apeSettings: AperantConnectionSettings
    @State private var draftURL = ""
    @State private var draftKey = ""
    @State private var revealsKey = false
    @State private var saved = false

    var body: some View {
        SectionCard(title: "Bridge Aperant", eyebrow: "aperant-bridge", tilt: 0.6, accent: MascaradeTheme.blue) {
            Text("L'app parle au bridge HTTP sur Tower (port 3200 par défaut). Si BRIDGE_API_KEY est configurée dans Docker, renseigne-la ici.")
                .font(.system(.body, design: .rounded))
                .foregroundStyle(MascaradeTheme.foreground)

            VStack(alignment: .leading, spacing: 10) {
                Text("Bridge URL")
                    .font(.system(.caption, design: .rounded).weight(.medium))
                    .foregroundStyle(MascaradeTheme.muted)
                TextField("http://tower:3200", text: $draftURL)
                    .textFieldStyle(.roundedBorder)
                    .autocorrectionDisabled()
                    .onAppear { draftURL = apeSettings.normalizedBaseURL }
            }

            VStack(alignment: .leading, spacing: 10) {
                Text("Bridge API Key")
                    .font(.system(.caption, design: .rounded).weight(.medium))
                    .foregroundStyle(MascaradeTheme.muted)
                HStack {
                    Group {
                        if revealsKey {
                            TextField("Laisser vide si pas d'auth", text: $draftKey)
                        } else {
                            SecureField("Laisser vide si pas d'auth", text: $draftKey)
                        }
                    }
                    .textFieldStyle(.roundedBorder)
                    .autocorrectionDisabled()
                    Button {
                        revealsKey.toggle()
                    } label: {
                        Image(systemName: revealsKey ? "eye.slash" : "eye")
                    }
                    .buttonStyle(.borderless)
                }
            }

            HStack(spacing: 12) {
                Button(saved ? "Sauvegardé ✓" : "Sauvegarder") {
                    apeSettings.update(baseURL: draftURL, apiKey: draftKey)
                    withAnimation { saved = true }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                        withAnimation { saved = false }
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(saved)

                if apeSettings.apiKeyIsSet {
                    CapsuleLabel(text: "clé configurée", tone: MascaradeTheme.success)
                } else {
                    CapsuleLabel(text: "sans auth", tone: MascaradeTheme.muted)
                }
            }
        }
    }
}

//
//  LocalCockpitView.swift
//  Mascarade
//

import CoreData
import SwiftUI

struct LocalCockpitView: View {
    @ObservedObject var frappeSettings: FrappeConnectionSettings
    @ObservedObject var frappeViewModel: FrappeViewModel
    @ObservedObject var frappeRealtime: FrappeRealtimeService

    @EnvironmentObject private var persistenceController: PersistenceController
    @Environment(\.managedObjectContext) private var viewContext
    @FetchRequest(
        sortDescriptors: [NSSortDescriptor(keyPath: \VaultEntry.updatedAt, ascending: false)],
        animation: .snappy
    )
    private var entries: FetchedResults<VaultEntry>

    @State private var searchText = ""
    @State private var debouncedSearch = ""
    @State private var selectedStatus = EntryStatusFilter.all
    @State private var selectedProject = "Tous"
    @State private var showArchived = false
    @State private var editorSession: EntryEditorSession?
    @State private var bannerMessage: String?
    @State private var viewMode: CockpitViewMode = .list

    private var projectOptions: [String] {
        ["Tous"] + Array(Set(entries.map(\.safeProject))).sorted()
    }

    private var visibleEntries: [VaultEntry] {
        entries.filter { entry in
            let projectMatches = selectedProject == "Tous" || entry.safeProject == selectedProject
            let statusMatches = selectedStatus.entryStatus.map { entry.safeStatus == $0 } ?? true
            let archiveMatches = showArchived || !entry.isArchived
            let searchMatches = debouncedSearch.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || [
                entry.safeTitle,
                entry.safeProject,
                entry.safeSource,
                entry.content ?? ""
            ]
            .joined(separator: " ")
            .localizedCaseInsensitiveContains(debouncedSearch)
            return projectMatches && statusMatches && archiveMatches && searchMatches
        }
    }

    private var liveEntries: [VaultEntry] {
        entries.filter { !$0.isArchived }
    }

    private var blockedCount: Int { liveEntries.filter { $0.safeStatus == .blocked }.count }
    private var activeCount: Int { liveEntries.filter { $0.safeStatus == .active }.count }
    private var projectCount: Int { Set(liveEntries.map(\.safeProject)).count }

    var body: some View {
        Group {
            if viewMode == .kanban {
                kanbanLayout
            } else {
                listLayout
            }
        }
        .task(id: searchText) {
            let query = searchText
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled else { return }
            debouncedSearch = query
        }
        .task {
            guard frappeSettings.isConfigured else { return }
            await frappeViewModel.refresh(using: frappeSettings)
        }
        .navigationTitle("Cockpit")
        .searchable(text: $searchText, prompt: "Chercher dans le cockpit")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    editorSession = EntryEditorSession(draft: .empty)
                } label: {
                    Label("Nouvelle entree", systemImage: "plus")
                }
            }
        }
        .sheet(item: $editorSession) { session in
            NavigationStack {
                VaultEntryEditor(initialDraft: session.draft)
            }
        }
        .alert(
            "Cockpit local",
            isPresented: Binding(
                get: { bannerMessage != nil },
                set: { if !$0 { bannerMessage = nil } }
            )
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(bannerMessage ?? "")
        }
    }

    // MARK: - Layout liste

    private var listLayout: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                cockpitHeader
                metricsBand
                controlDeck
                listDeck
            }
            .padding(20)
            .padding(.bottom, 36)
        }
    }

    // MARK: - Layout kanban

    private var kanbanLayout: some View {
        VStack(alignment: .leading, spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    metricsBand
                    kanbanControlDeck
                }
                .padding(.horizontal, 20)
                .padding(.top, 16)
                .padding(.bottom, 12)
            }
            .scrollBounceBehavior(.basedOnSize)
            .frame(maxHeight: 230)

            // Bannière d'erreur Frappe
            if let banner = frappeViewModel.bannerMessage {
                HStack(spacing: 8) {
                    Image(systemName: "exclamationmark.circle.fill")
                        .foregroundStyle(MascaradeTheme.error)
                    Text(banner)
                        .font(.caption)
                        .foregroundStyle(MascaradeTheme.error)
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 8)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }

            if !frappeSettings.isConfigured {
                frappeUnconfiguredState
            } else {
                KanbanBoardView(
                    frappeViewModel: frappeViewModel,
                    frappeSettings: frappeSettings
                )
                .padding(.horizontal, 20)
                .padding(.bottom, 12)
            }
        }
    }

    // MARK: - Etat non-configuré

    private var frappeUnconfiguredState: some View {
        VStack(spacing: 20) {
            ZStack {
                Circle()
                    .fill(MascaradeTheme.amber.opacity(0.12))
                    .frame(width: 72, height: 72)
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 30))
                    .foregroundStyle(MascaradeTheme.amber)
            }
            VStack(spacing: 6) {
                Text("Frappe non configuré")
                    .font(.headline)
                    .foregroundStyle(MascaradeTheme.foreground)
                Text("Configure l'URL dans l'onglet Rituel pour activer le kanban.")
                    .font(.subheadline)
                    .foregroundStyle(MascaradeTheme.muted)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(40)
    }

    // MARK: - Kanban control deck

    private var kanbanControlDeck: some View {
        HStack(spacing: 10) {
            // Toggle vue
            Picker("Vue", selection: $viewMode) {
                ForEach(CockpitViewMode.allCases, id: \.self) { mode in
                    Label(mode.title, systemImage: mode.systemImage).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 190)

            Spacer(minLength: 0)

            // Indicateur Socket.io
            HStack(spacing: 5) {
                Circle()
                    .fill(frappeRealtime.isConnected ? MascaradeTheme.success : MascaradeTheme.muted)
                    .frame(width: 7, height: 7)
                Text(frappeRealtime.isConnected ? "live" : "offline")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(frappeRealtime.isConnected ? MascaradeTheme.success : MascaradeTheme.muted)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(
                (frappeRealtime.isConnected ? MascaradeTheme.success : MascaradeTheme.muted).opacity(0.10)
            )
            .clipShape(Capsule())

            // Filtre projet Frappe
            let frappeProjects = Array(Set(frappeViewModel.tasks.compactMap(\.project))).sorted()
            if !frappeProjects.isEmpty {
                Menu {
                    Button("Tous les projets") {
                        frappeViewModel.selectedProjectFilter = nil
                    }
                    Divider()
                    ForEach(frappeProjects, id: \.self) { p in
                        Button(p) { frappeViewModel.selectedProjectFilter = p }
                    }
                } label: {
                    HStack(spacing: 5) {
                        Image(systemName: "tray.full")
                            .font(.caption)
                        Text(frappeViewModel.selectedProjectFilter ?? "Projet")
                            .font(.caption.weight(.medium))
                        Image(systemName: "chevron.down")
                            .font(.system(size: 9, weight: .semibold))
                    }
                    .foregroundStyle(MascaradeTheme.foreground)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 7)
                    .background(MascaradeTheme.panel)
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .stroke(MascaradeTheme.rule, lineWidth: 1)
                    }
                }
                .buttonStyle(.plain)
            }

            // Rafraîchir
            Button {
                Task { await frappeViewModel.refresh(using: frappeSettings, force: true) }
            } label: {
                Image(systemName: frappeViewModel.isRefreshing ? "arrow.clockwise" : "arrow.clockwise")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(MascaradeTheme.signal)
                    .rotationEffect(.degrees(frappeViewModel.isRefreshing ? 360 : 0))
                    .animation(
                        frappeViewModel.isRefreshing
                            ? .linear(duration: 0.9).repeatForever(autoreverses: false)
                            : .default,
                        value: frappeViewModel.isRefreshing
                    )
                    .frame(width: 32, height: 32)
                    .background(MascaradeTheme.signal.opacity(0.10))
                    .clipShape(Circle())
            }
            .buttonStyle(.plain)
            .disabled(frappeViewModel.isRefreshing)
        }
        .padding(14)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(MascaradeTheme.rule, lineWidth: 1)
        }
        .shadow(color: MascaradeTheme.shadow, radius: 6, x: 0, y: 3)
    }

    // MARK: - Cockpit header

    private var cockpitHeader: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Hero artwork
            MascaradeArtworkBanner(
                assetName: "CockpitHero",
                eyebrow: "electron fou",
                title: "Cockpit local-first",
                detail: "papier, cuivre, fils nerveux et traces qui restent quand le gateway tombe",
                height: 172
            )

            // Barre d'infos sous la bannière
            HStack(alignment: .center, spacing: 14) {
                // Icône de sync
                ZStack {
                    Circle()
                        .fill(MascaradeTheme.signal.opacity(0.12))
                        .frame(width: 38, height: 38)
                    Image(systemName: persistenceController.syncStatus.systemImage)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(MascaradeTheme.signal)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text("Cockpit local-first")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(MascaradeTheme.foreground)
                    Text(persistenceController.syncStatus.message)
                        .font(.caption)
                        .foregroundStyle(MascaradeTheme.muted)
                }

                Spacer(minLength: 12)

                Button {
                    do {
                        try persistenceController.seedIfNeeded()
                        bannerMessage = "Le socle local est verifié."
                    } catch {
                        bannerMessage = error.localizedDescription
                    }
                } label: {
                    Label("Vérifier", systemImage: "sparkles")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(MascaradeTheme.signal)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 7)
                        .background(MascaradeTheme.signal.opacity(0.10))
                        .clipShape(Capsule())
                        .overlay {
                            Capsule().stroke(MascaradeTheme.signal.opacity(0.25), lineWidth: 1)
                        }
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 14)
            .background(MascaradeTheme.card)
        }
        .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 26, style: .continuous)
                .stroke(MascaradeTheme.rule, lineWidth: 1)
        }
        .shadow(color: MascaradeTheme.shadow, radius: 12, x: 0, y: 8)
    }

    // MARK: - Metrics band

    private var metricsBand: some View {
        let metrics: [(title: String, value: String, note: String, tone: Color)] = viewMode == .kanban
            ? [
                ("Tâches Frappe",  "\(frappeViewModel.tasks.count)",                                         frappeViewModel.isOnline == true ? "frappe en ligne" : "frappe hors ligne", frappeViewModel.isOnline == true ? MascaradeTheme.success : MascaradeTheme.muted),
                ("En cours",       "\(frappeViewModel.tasks.filter { $0.taskStatus == .working }.count)",    "working",        MascaradeTheme.blue),
                ("En révision",    "\(frappeViewModel.tasks.filter { $0.taskStatus == .pendingReview }.count)", "pending review", MascaradeTheme.amber),
                ("Terminées",      "\(frappeViewModel.tasks.filter { $0.taskStatus == .completed }.count)", "completed",      MascaradeTheme.success),
            ]
            : [
                ("Entrées",    "\(visibleEntries.count)",  debouncedSearch.isEmpty ? "dans le cockpit" : "après filtrage", MascaradeTheme.signal),
                ("Actives",    "\(activeCount)",           "hors archives",          MascaradeTheme.success),
                ("Bloquées",   "\(blockedCount)",          "à remettre sous lampe",  MascaradeTheme.error),
                ("Projets",    "\(projectCount)",          "surfaces suivies",       MascaradeTheme.blue),
            ]

        return LazyVGrid(
            columns: [GridItem(.adaptive(minimum: 148), spacing: 12)],
            spacing: 12
        ) {
            ForEach(metrics, id: \.title) { m in
                CockpitMetricCard(title: m.title, value: m.value, note: m.note, tone: m.tone)
            }
        }
        .animation(.spring(response: 0.4, dampingFraction: 0.82), value: viewMode)
    }

    // MARK: - Control deck (mode liste)

    private var controlDeck: some View {
        VStack(alignment: .leading, spacing: 14) {
            // Ligne 1 : toggle vue + mode kanban
            HStack(spacing: 12) {
                Label("Vue", systemImage: "square.grid.2x2")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(MascaradeTheme.muted)

                Picker("Vue", selection: $viewMode) {
                    ForEach(CockpitViewMode.allCases, id: \.self) { mode in
                        Label(mode.title, systemImage: mode.systemImage).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 200)

                Spacer(minLength: 0)
            }

            // Ligne 2 : filtre statut (liste uniquement)
            if viewMode == .list {
                VStack(alignment: .leading, spacing: 6) {
                    Label("Statut", systemImage: "tag")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(MascaradeTheme.muted)

                    Picker("Etat", selection: $selectedStatus) {
                        ForEach(EntryStatusFilter.allCases) { status in
                            Text(status.title).tag(status)
                        }
                    }
                    .pickerStyle(.segmented)
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }

            // Ligne 3 : projet + archives
            HStack(spacing: 10) {
                Menu {
                    Picker("Projet", selection: $selectedProject) {
                        ForEach(projectOptions, id: \.self) { project in
                            Text(project).tag(project)
                        }
                    }
                } label: {
                    HStack(spacing: 5) {
                        Image(systemName: "tray.full")
                            .font(.caption)
                        Text(selectedProject)
                            .font(.caption.weight(.medium))
                        Image(systemName: "chevron.down")
                            .font(.system(size: 9, weight: .semibold))
                    }
                    .foregroundStyle(MascaradeTheme.foreground)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(MascaradeTheme.card.opacity(0.7))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .stroke(MascaradeTheme.rule, lineWidth: 1)
                    }
                }
                .buttonStyle(.plain)

                Spacer(minLength: 0)

                // Toggle archives avec style pill
                Button {
                    withAnimation(.spring(response: 0.36, dampingFraction: 0.82)) {
                        showArchived.toggle()
                    }
                } label: {
                    HStack(spacing: 5) {
                        Image(systemName: showArchived ? "archivebox.fill" : "archivebox")
                            .font(.caption)
                        Text(showArchived ? "Archives visibles" : "Archives cachées")
                            .font(.caption.weight(.medium))
                    }
                    .foregroundStyle(showArchived ? MascaradeTheme.amber : MascaradeTheme.muted)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(
                        (showArchived ? MascaradeTheme.amber : MascaradeTheme.muted).opacity(0.10)
                    )
                    .clipShape(Capsule())
                    .overlay {
                        Capsule()
                            .stroke(
                                (showArchived ? MascaradeTheme.amber : MascaradeTheme.muted).opacity(0.25),
                                lineWidth: 1
                            )
                    }
                }
                .buttonStyle(.plain)
            }
        }
        .padding(18)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(MascaradeTheme.rule, lineWidth: 1)
        }
        .shadow(color: MascaradeTheme.shadow, radius: 6, x: 0, y: 3)
        .animation(.spring(response: 0.42, dampingFraction: 0.85), value: viewMode)
    }

    // MARK: - List deck

    private var listDeck: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Entrées")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(MascaradeTheme.foreground)
                Spacer()
                Text("\(visibleEntries.count)")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(MascaradeTheme.muted)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(MascaradeTheme.muted.opacity(0.10))
                    .clipShape(Capsule())
            }

            if visibleEntries.isEmpty {
                HStack(spacing: 12) {
                    Image(systemName: "tray")
                        .font(.title3)
                        .foregroundStyle(MascaradeTheme.muted)
                    Text("Aucune entrée ne correspond aux filtres actuels.")
                        .font(.subheadline)
                        .foregroundStyle(MascaradeTheme.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(20)
                .background(MascaradeTheme.panel)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(MascaradeTheme.rule, lineWidth: 1)
                }
            } else {
                ForEach(visibleEntries) { entry in
                    Button {
                        editorSession = EntryEditorSession(draft: EntryDraft(entry: entry))
                    } label: {
                        VaultEntryRow(entry: entry)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }
}

// MARK: - Types internes

struct EntryEditorSession: Identifiable {
    let id = UUID()
    let draft: EntryDraft
}

// MARK: - Composants privés

private struct CockpitMetricCard: View {
    let title: String
    let value: String
    let note: String
    let tone: Color

    @State private var isHovered = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Circle()
                    .fill(tone)
                    .frame(width: 7, height: 7)
                Text(title.uppercased())
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundStyle(MascaradeTheme.muted)
            }

            Text(value)
                .font(.system(size: 30, weight: .bold, design: .rounded))
                .foregroundStyle(MascaradeTheme.foreground)

            Text(note)
                .font(.caption)
                .foregroundStyle(MascaradeTheme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(
            ZStack {
                tone.opacity(isHovered ? 0.16 : 0.09)
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(Color.white.opacity(0.35))
            }
        )
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(tone.opacity(isHovered ? 0.40 : 0.22), lineWidth: 1)
        }
        .scaleEffect(isHovered ? 1.015 : 1.0)
        .shadow(color: tone.opacity(isHovered ? 0.15 : 0.05), radius: isHovered ? 10 : 4, x: 0, y: 3)
        .animation(.spring(response: 0.3, dampingFraction: 0.75), value: isHovered)
        .onHover { isHovered = $0 }
    }
}

private struct VaultEntryRow: View {
    let entry: VaultEntry
    @State private var isHovered = false

    private var updatedLabel: String {
        guard let updatedAt = entry.updatedAt else { return "jamais modifiée" }
        return RelativeDateTimeFormatter.mascarade.localizedString(for: updatedAt, relativeTo: Date())
    }

    private var statusToneLocal: Color {
        switch entry.safeStatus {
        case .backlog:  return MascaradeTheme.muted
        case .active:   return MascaradeTheme.blue
        case .blocked:  return MascaradeTheme.error
        case .done:     return MascaradeTheme.success
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            // Barre de statut
            RoundedRectangle(cornerRadius: 2)
                .fill(statusToneLocal)
                .frame(width: 3)
                .padding(.vertical, 4)

            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(entry.safeTitle)
                        .font(.headline)
                        .foregroundStyle(MascaradeTheme.foreground)

                    Spacer(minLength: 8)

                    Text("Mis à jour \(updatedLabel)")
                        .font(.caption)
                        .foregroundStyle(MascaradeTheme.muted)
                }

                if let previewLine = entry.content?.prefix(120), !previewLine.isEmpty {
                    Text(previewLine)
                        .font(.subheadline)
                        .foregroundStyle(MascaradeTheme.muted)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                }

                HStack(spacing: 6) {
                    CockpitPill(text: entry.safeProject, tone: MascaradeTheme.blue)
                    CockpitPill(text: entry.safeEntryKind.title, tone: MascaradeTheme.signal)
                    CockpitPill(text: entry.safeStatus.title, tone: statusToneLocal)
                    if !entry.safeSource.isEmpty {
                        CockpitPill(text: entry.safeSource, tone: MascaradeTheme.panelBorder)
                    }
                    Spacer(minLength: 0)
                    Image(systemName: entry.isArchived ? "archivebox.fill" : "chevron.right")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(entry.isArchived ? MascaradeTheme.panelBorder : MascaradeTheme.signal)
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .background(
            isHovered
                ? MascaradeTheme.panel.opacity(0.9)
                : MascaradeTheme.panel
        )
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(
                    isHovered ? MascaradeTheme.panelBorder.opacity(0.5) : MascaradeTheme.rule,
                    lineWidth: isHovered ? 1.5 : 1
                )
        }
        .scaleEffect(isHovered ? 1.004 : 1.0)
        .shadow(color: MascaradeTheme.shadow.opacity(isHovered ? 2 : 1), radius: isHovered ? 10 : 4, x: 0, y: 2)
        .animation(.spring(response: 0.28, dampingFraction: 0.78), value: isHovered)
        .onHover { isHovered = $0 }
    }
}

struct CockpitPill: View {
    let text: String
    let tone: Color

    var body: some View {
        Text(text)
            .font(.system(size: 10, weight: .semibold))
            .foregroundStyle(tone)
            .padding(.horizontal, 9)
            .padding(.vertical, 4)
            .background(tone.opacity(0.12))
            .clipShape(Capsule())
            .overlay {
                Capsule()
                    .stroke(tone.opacity(0.28), lineWidth: 1)
            }
    }
}

private struct VaultEntryEditor: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.managedObjectContext) private var viewContext

    @State private var draft: EntryDraft
    @State private var errorMessage: String?
    @State private var showDeleteConfirmation = false

    private let store = VaultStore()

    init(initialDraft: EntryDraft) {
        _draft = State(initialValue: initialDraft)
    }

    private var isExistingEntry: Bool { draft.id != nil }

    var body: some View {
        Form {
            Section("Identite") {
                TextField("Titre", text: $draft.title)
                TextField("Projet", text: $draft.project)
                TextField("Source", text: $draft.source)
            }

            Section("Nature") {
                Picker("Type", selection: $draft.entryKind) {
                    ForEach(EntryKind.allCases) { kind in
                        Label(kind.title, systemImage: kind.systemImage).tag(kind)
                    }
                }

                Picker("Etat", selection: $draft.status) {
                    ForEach(EntryStatus.allCases) { status in
                        Text(status.title).tag(status)
                    }
                }

                Toggle("Editable par agent", isOn: $draft.agentWritable)
            }

            Section("Contenu") {
                TextField("Content type", text: $draft.contentType)
                TextEditor(text: $draft.content)
                    .frame(minHeight: 220)
            }

            if isExistingEntry {
                Section("Actions") {
                    Button(draft.id.flatMap(fetchEntry)?.isArchived == true ? "Restaurer" : "Archiver") {
                        archiveOrRestore()
                    }

                    Button("Supprimer", role: .destructive) {
                        showDeleteConfirmation = true
                    }
                }
            }
        }
        .navigationTitle(isExistingEntry ? "Editer l'entree" : "Nouvelle entree")
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Fermer") { dismiss() }
            }
            ToolbarItem(placement: .confirmationAction) {
                Button("Enregistrer") { saveEntry() }
            }
        }
        .alert(
            "Store local",
            isPresented: Binding(
                get: { errorMessage != nil },
                set: { if !$0 { errorMessage = nil } }
            )
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(errorMessage ?? "")
        }
        .confirmationDialog(
            "Supprimer cette entree ?",
            isPresented: $showDeleteConfirmation,
            titleVisibility: .visible
        ) {
            Button("Supprimer", role: .destructive) { deleteEntry() }
            Button("Annuler", role: .cancel) {}
        } message: {
            Text("Cette action est irreversible.")
        }
    }

    private func saveEntry() {
        do {
            try store.saveEntry(from: draft, in: viewContext)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func archiveOrRestore() {
        guard let objectID = draft.id, let entry = fetchEntry(objectID) else {
            errorMessage = VaultStoreError.missingEntry.localizedDescription
            return
        }
        do {
            if entry.isArchived {
                try store.restore(entry, in: viewContext)
            } else {
                try store.archive(entry, in: viewContext)
            }
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func deleteEntry() {
        guard let objectID = draft.id, let entry = fetchEntry(objectID) else {
            errorMessage = VaultStoreError.missingEntry.localizedDescription
            return
        }
        do {
            try store.delete(entry, in: viewContext)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func fetchEntry(_ objectID: NSManagedObjectID) -> VaultEntry? {
        try? store.fetchEntry(id: objectID, in: viewContext)
    }
}

// MARK: - Helpers

/// Couleur associée à un statut d'entrée locale (VaultEntry)
private func statusTone(_ status: EntryStatus) -> Color {
    switch status {
    case .backlog:  return MascaradeTheme.muted
    case .active:   return MascaradeTheme.blue
    case .blocked:  return MascaradeTheme.error
    case .done:     return MascaradeTheme.success
    }
}

#Preview {
    NavigationStack {
        LocalCockpitView(
            frappeSettings: FrappeConnectionSettings(),
            frappeViewModel: FrappeViewModel(),
            frappeRealtime: FrappeRealtimeService()
        )
        .environment(\.managedObjectContext, PersistenceController.preview.container.viewContext)
        .environmentObject(PersistenceController.preview)
    }
}

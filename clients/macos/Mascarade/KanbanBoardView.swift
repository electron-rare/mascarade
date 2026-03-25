//
//  KanbanBoardView.swift
//  Mascarade
//
//  Kanban alimenté par les tâches Frappe.
//  Colonnes : Open · Working · Pending Review · Completed.
//  Drag-and-drop entre colonnes → PUT status via FrappeAPI.
//

import SwiftUI
import UniformTypeIdentifiers

// MARK: - Mode d'affichage du Cockpit

enum CockpitViewMode: String, CaseIterable {
    case list   = "list"
    case kanban = "kanban"

    var title: String {
        switch self {
        case .list:   return "Liste"
        case .kanban: return "Kanban"
        }
    }

    var systemImage: String {
        switch self {
        case .list:   return "list.bullet"
        case .kanban: return "square.grid.3x1.below.line.grid.1x2"
        }
    }
}

// MARK: - Colonnes Kanban

private let kanbanColumns: [FrappeTaskStatus] = [.open, .working, .pendingReview, .completed]

// MARK: - Board principal

struct KanbanBoardView: View {
    @ObservedObject var frappeViewModel: FrappeViewModel
    @ObservedObject var frappeSettings: FrappeConnectionSettings

    @State private var selectedTask: FrappeTask?
    @State private var newTaskStatus: FrappeTaskStatus?

    private func columnTasks(for status: FrappeTaskStatus) -> [FrappeTask] {
        frappeViewModel.filteredTasks.filter { $0.taskStatus == status }
    }

    var body: some View {
        GeometryReader { proxy in
            let w = proxy.size.width > 0 ? proxy.size.width : 320
            let fits4 = w >= 1040
            let colWidth = fits4
                ? (w - 64) / 4
                : max(240, (w - 48) / 2)

            let board = boardContent(colWidth: colWidth)

            if fits4 {
                board
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    board.padding(.horizontal, 4).padding(.bottom, 8)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .overlay(alignment: .center) {
            if frappeViewModel.isRefreshing && frappeViewModel.tasks.isEmpty {
                loadingOverlay
            }
        }
        .sheet(item: $selectedTask) { task in
            FrappeTaskDetailSheet(task: task)
        }
        .sheet(item: $newTaskStatus) { status in
            FrappeCreateTaskSheet(
                initialStatus: status,
                projects: frappeViewModel.projects,
                frappeSettings: frappeSettings
            ) {
                await frappeViewModel.refresh(using: frappeSettings, force: true)
            }
        }
    }

    @ViewBuilder
    private func boardContent(colWidth: CGFloat) -> some View {
        HStack(alignment: .top, spacing: 12) {
            ForEach(kanbanColumns, id: \.self) { status in
                FrappeKanbanColumn(
                    status: status,
                    tasks: columnTasks(for: status),
                    projects: frappeViewModel.projects,
                    isRefreshing: frappeViewModel.isRefreshing,
                    onTap: { task in selectedTask = task },
                    onMove: { task, newStatus in
                        Task { await move(task: task, to: newStatus) }
                    },
                    onCreate: { newTaskStatus = status }
                )
                .frame(width: colWidth)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }

    private var loadingOverlay: some View {
        HStack(spacing: 10) {
            ProgressView()
                .progressViewStyle(.circular)
                .tint(MascaradeTheme.signal)
            Text("Chargement Frappe…")
                .font(.system(.subheadline, design: .rounded))
                .foregroundStyle(MascaradeTheme.muted)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .shadow(color: MascaradeTheme.shadow, radius: 12, y: 4)
    }

    // MARK: - Move

    private func move(task: FrappeTask, to newStatus: FrappeTaskStatus) async {
        guard let baseURL = frappeSettings.resolvedBaseURL() else { return }
        let client = FrappeAPI(baseURL: baseURL, authHeader: frappeSettings.authorizationHeader)
        do {
            try await client.updateTaskStatus(name: task.name, status: newStatus.rawValue)
            await frappeViewModel.refresh(using: frappeSettings, force: true)
        } catch {
            await frappeViewModel.setBanner("Déplacement échoué : \(error.localizedDescription)")
        }
    }
}

// MARK: - Colonne

private struct FrappeKanbanColumn: View {
    let status: FrappeTaskStatus
    let tasks: [FrappeTask]
    let projects: [FrappeProject]
    let isRefreshing: Bool
    let onTap: (FrappeTask) -> Void
    let onMove: (FrappeTask, FrappeTaskStatus) -> Void
    let onCreate: () -> Void

    @State private var isDropTargeted = false

    private var tone: Color { frappeStatusTone(status) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            columnHeader
                .padding(.horizontal, 14)
                .padding(.top, 14)
                .padding(.bottom, 10)

            // Barre de couleur sous le header
            tone
                .frame(height: 2)
                .opacity(0.5)

            ScrollView(.vertical, showsIndicators: false) {
                LazyVStack(spacing: 8) {
                    ForEach(tasks) { task in
                        FrappeKanbanCard(task: task)
                            .draggable(FrappeTaskTransfer(name: task.name, status: status.rawValue)) {
                                FrappeKanbanCard(task: task)
                                    .frame(width: 230)
                                    .opacity(0.9)
                                    .scaleEffect(0.97)
                            }
                            .onTapGesture { onTap(task) }
                            .transition(.asymmetric(
                                insertion: .move(edge: .top).combined(with: .opacity),
                                removal: .opacity
                            ))
                    }

                    if tasks.isEmpty {
                        emptyState
                    }
                }
                .padding(12)
                .animation(.spring(response: 0.38, dampingFraction: 0.82), value: tasks.map(\.id))
            }

            addButton
                .padding(.horizontal, 12)
                .padding(.bottom, 12)
                .padding(.top, 4)
        }
        .frame(maxHeight: .infinity, alignment: .top)
        .background {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(tone.opacity(isDropTargeted ? 0.11 : 0.05))
        }
        .overlay {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(
                    isDropTargeted ? tone.opacity(0.6) : MascaradeTheme.rule,
                    lineWidth: isDropTargeted ? 1.5 : 1
                )
        }
        .animation(.spring(response: 0.3, dampingFraction: 0.8), value: isDropTargeted)
        .dropDestination(for: FrappeTaskTransfer.self) { items, _ in
            for item in items where item.status != status.rawValue {
                onMove(FrappeTask(transferName: item.name, currentStatus: item.status), status)
            }
            return !items.isEmpty
        } isTargeted: { isDropTargeted = $0 }
    }

    // MARK: Header

    private var columnHeader: some View {
        HStack(spacing: 8) {
            // Dot coloré
            ZStack {
                Circle()
                    .fill(tone.opacity(0.18))
                    .frame(width: 28, height: 28)
                Circle()
                    .fill(tone)
                    .frame(width: 8, height: 8)
                    .shadow(color: tone.opacity(0.5), radius: 4)
            }

            VStack(alignment: .leading, spacing: 1) {
                Text(status.label.uppercased())
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundStyle(tone)
                    .tracking(1.2)
                Text("\(tasks.count) tâche\(tasks.count == 1 ? "" : "s")")
                    .font(.system(size: 11, design: .rounded))
                    .foregroundStyle(MascaradeTheme.muted)
            }

            Spacer(minLength: 0)

            // Badge count
            if tasks.count > 0 {
                Text("\(tasks.count)")
                    .font(.system(size: 12, weight: .bold, design: .rounded))
                    .foregroundStyle(tone)
                    .frame(width: 24, height: 24)
                    .background(tone.opacity(0.14))
                    .clipShape(Circle())
            }
        }
    }

    // MARK: Empty state

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: status.systemImage)
                .font(.system(size: 22))
                .foregroundStyle(tone.opacity(0.35))
            Text("Aucune tâche")
                .font(.system(.caption, design: .rounded))
                .foregroundStyle(MascaradeTheme.muted.opacity(0.6))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 28)
    }

    // MARK: Add button

    private var addButton: some View {
        Button(action: onCreate) {
            HStack(spacing: 6) {
                Image(systemName: "plus")
                    .font(.system(size: 11, weight: .bold))
                Text("Nouvelle tâche")
                    .font(.system(size: 12, weight: .medium, design: .rounded))
            }
            .foregroundStyle(tone.opacity(0.85))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 9)
            .background(tone.opacity(0.07))
            .overlay {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(tone.opacity(0.2), lineWidth: 1)
                    .strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [4, 3]))
                    .foregroundStyle(tone.opacity(0.3))
            }
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Carte tâche

struct FrappeKanbanCard: View {
    let task: FrappeTask

    @State private var isHovered = false

    private var tone: Color { frappeStatusTone(task.taskStatus) }
    private var isOverdue: Bool {
        guard let due = task.expEndDate else { return false }
        return due < String(Date().ISO8601Format().prefix(10)) && task.taskStatus != .completed
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {

            // Bandeau coloré en haut
            tone
                .frame(height: 3)
                .clipShape(RoundedRectangle(cornerRadius: 2))
                .padding(.bottom, 10)

            // Sujet
            Text(task.subject)
                .font(.system(.subheadline, design: .rounded).weight(.semibold))
                .foregroundStyle(MascaradeTheme.foreground)
                .lineLimit(2)
                .frame(maxWidth: .infinity, alignment: .leading)

            // Description
            if let desc = task.description, !desc.isEmpty {
                Text(desc)
                    .font(.system(size: 12, design: .rounded))
                    .foregroundStyle(MascaradeTheme.muted)
                    .lineLimit(2)
                    .padding(.top, 5)
            }

            // Footer : pills + date
            HStack(spacing: 5) {
                if let project = task.project, !project.isEmpty {
                    KanbanPill(text: project, tone: MascaradeTheme.blue, icon: "folder")
                }
                if let priority = task.priority, !priority.isEmpty {
                    KanbanPill(text: priority, tone: priorityTone(priority), icon: priorityIcon(priority))
                }
                Spacer(minLength: 0)
                if let due = task.expEndDate {
                    HStack(spacing: 3) {
                        Image(systemName: isOverdue ? "exclamationmark.circle.fill" : "calendar")
                            .font(.system(size: 9))
                        Text(due.prefix(10))
                            .font(.system(size: 10, design: .monospaced))
                    }
                    .foregroundStyle(isOverdue ? MascaradeTheme.error : MascaradeTheme.muted)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background((isOverdue ? MascaradeTheme.error : MascaradeTheme.muted).opacity(0.08))
                    .clipShape(Capsule())
                }
            }
            .padding(.top, 10)
        }
        .padding(12)
        .background(MascaradeTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(isHovered ? tone.opacity(0.35) : MascaradeTheme.rule, lineWidth: 1)
        }
        .shadow(color: MascaradeTheme.shadow.opacity(isHovered ? 0.16 : 0.08),
                radius: isHovered ? 8 : 4, x: 0, y: isHovered ? 4 : 2)
        .scaleEffect(isHovered ? 1.015 : 1.0)
        .animation(.spring(response: 0.28, dampingFraction: 0.8), value: isHovered)
        .contentShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .onHover { isHovered = $0 }
    }

    private func priorityTone(_ p: String) -> Color {
        switch p.lowercased() {
        case "urgent":  return MascaradeTheme.error
        case "high":    return Color(red: 0.80, green: 0.42, blue: 0.18)
        case "medium":  return MascaradeTheme.amber
        default:        return MascaradeTheme.muted
        }
    }

    private func priorityIcon(_ p: String) -> String {
        switch p.lowercased() {
        case "urgent":  return "flame.fill"
        case "high":    return "arrow.up.circle.fill"
        case "medium":  return "minus.circle"
        default:        return "arrow.down.circle"
        }
    }
}

// MARK: - Pill inline pour cartes

private struct KanbanPill: View {
    let text: String
    let tone: Color
    let icon: String

    var body: some View {
        HStack(spacing: 3) {
            Image(systemName: icon)
                .font(.system(size: 9))
            Text(text)
                .font(.system(size: 10, weight: .medium, design: .rounded))
                .lineLimit(1)
        }
        .foregroundStyle(tone)
        .padding(.horizontal, 6)
        .padding(.vertical, 3)
        .background(tone.opacity(0.12))
        .clipShape(Capsule())
    }
}

// MARK: - Détail tâche

struct FrappeTaskDetailSheet: View {
    let task: FrappeTask
    @Environment(\.dismiss) private var dismiss

    private var tone: Color { frappeStatusTone(task.taskStatus) }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {

                    // Hero status bar
                    statusHero
                        .padding(.horizontal, 20)
                        .padding(.top, 4)

                    // Sujet + description
                    SectionCard(title: task.name, eyebrow: "TÂCHE", tilt: -0.4) {
                        Text(task.subject)
                            .font(.system(.title3, design: .rounded).weight(.semibold))
                            .foregroundStyle(MascaradeTheme.foreground)
                            .frame(maxWidth: .infinity, alignment: .leading)

                        if let desc = task.description, !desc.isEmpty {
                            Divider().overlay(MascaradeTheme.rule).padding(.vertical, 4)
                            Text(desc)
                                .font(.system(.callout, design: .rounded))
                                .foregroundStyle(MascaradeTheme.foreground.opacity(0.8))
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .textSelection(.enabled)
                        }
                    }

                    // Méta données
                    if hasMetadata {
                        SectionCard(title: "Détails", eyebrow: "META", tilt: 0.3) {
                            if let project = task.project, !project.isEmpty {
                                MetricRow(label: "Projet", value: project)
                            }
                            if let assignee = task.firstAssignee, !assignee.isEmpty {
                                MetricRow(label: "Assigné à", value: assignee)
                            }
                            if let due = task.expEndDate, !due.isEmpty {
                                MetricRow(label: "Échéance", value: String(due.prefix(10)))
                            }
                            if let modified = task.modified {
                                MetricRow(label: "Modifié", value: String(modified.prefix(16)).replacingOccurrences(of: "T", with: " "))
                            }
                        }
                    }
                }
                .padding(.vertical, 12)
                .padding(.bottom, 24)
            }
            .background(MascaradeTheme.card.opacity(0.4))
            .navigationTitle(task.subject)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Fermer") { dismiss() }
                        .foregroundStyle(MascaradeTheme.signal)
                }
            }
        }
    }

    private var statusHero: some View {
        HStack(spacing: 10) {
            // Status badge
            HStack(spacing: 6) {
                Image(systemName: task.taskStatus.systemImage)
                    .font(.system(size: 13, weight: .semibold))
                Text(task.taskStatus.label)
                    .font(.system(.subheadline, design: .rounded).weight(.semibold))
            }
            .foregroundStyle(tone)
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(tone.opacity(0.12))
            .clipShape(Capsule())

            if let priority = task.priority, !priority.isEmpty {
                Text(priority)
                    .font(.system(.caption, design: .rounded).weight(.medium))
                    .foregroundStyle(MascaradeTheme.amber)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(MascaradeTheme.amber.opacity(0.1))
                    .clipShape(Capsule())
            }

            Spacer()

            if let due = task.expEndDate {
                HStack(spacing: 4) {
                    Image(systemName: "calendar")
                        .font(.system(size: 11))
                    Text(String(due.prefix(10)))
                        .font(.system(size: 12, design: .monospaced))
                }
                .foregroundStyle(MascaradeTheme.muted)
            }
        }
    }

    private var hasMetadata: Bool {
        (task.project != nil && !(task.project?.isEmpty ?? true))
        || task.firstAssignee != nil
        || task.expEndDate != nil
        || task.modified != nil
    }
}

// MARK: - Transferable drag-and-drop

struct FrappeTaskTransfer: Codable, Transferable {
    let name: String
    let status: String

    static var transferRepresentation: some TransferRepresentation {
        CodableRepresentation(contentType: .json)
    }
}

// MARK: - Extension FrappeTask pour drag-and-drop

extension FrappeTask {
    init(transferName: String, currentStatus: String) {
        self.init(
            name: transferName,
            subject: "",
            status: currentStatus,
            priority: nil,
            project: nil,
            assign: nil,
            description: nil,
            expEndDate: nil,
            modified: nil
        )
    }
}

// MARK: - Couleur par statut Frappe

func frappeStatusTone(_ status: FrappeTaskStatus) -> Color {
    switch status {
    case .open:          return MascaradeTheme.muted
    case .working:       return MascaradeTheme.blue
    case .pendingReview: return MascaradeTheme.amber
    case .overdue:       return MascaradeTheme.error
    case .template:      return MascaradeTheme.panelBorder
    case .cancelled:     return MascaradeTheme.error
    case .completed:     return MascaradeTheme.success
    }
}

// MARK: - Sheet de création de tâche

struct FrappeCreateTaskSheet: View {
    let initialStatus: FrappeTaskStatus
    let projects: [FrappeProject]
    let frappeSettings: FrappeConnectionSettings
    let onCreated: () async -> Void

    @Environment(\.dismiss) private var dismiss

    @State private var subject = ""
    @State private var selectedStatus: FrappeTaskStatus
    @State private var selectedPriority = "Medium"
    @State private var selectedProject = ""
    @State private var taskDescription = ""
    @State private var expEndDate: Date? = nil
    @State private var showDatePicker = false
    @State private var isSaving = false
    @State private var errorMessage: String?

    private let priorities = ["Low", "Medium", "High", "Urgent"]
    private let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    init(
        initialStatus: FrappeTaskStatus,
        projects: [FrappeProject],
        frappeSettings: FrappeConnectionSettings,
        onCreated: @escaping () async -> Void
    ) {
        self.initialStatus = initialStatus
        self.projects = projects
        self.frappeSettings = frappeSettings
        self.onCreated = onCreated
        _selectedStatus = State(initialValue: initialStatus)
    }

    private var tone: Color { frappeStatusTone(selectedStatus) }
    private var canSave: Bool { !subject.trimmingCharacters(in: .whitespaces).isEmpty && !isSaving }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {

                    // Champ sujet proéminent
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Sujet", systemImage: "text.cursor")
                            .font(.system(.caption, design: .rounded).weight(.semibold))
                            .foregroundStyle(MascaradeTheme.muted)
                        TextField("Titre de la tâche…", text: $subject, axis: .vertical)
                            .font(.system(.body, design: .rounded).weight(.medium))
                            .lineLimit(1...3)
                            .padding(12)
                            .background(MascaradeTheme.card)
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                            .overlay {
                                RoundedRectangle(cornerRadius: 12, style: .continuous)
                                    .stroke(subject.isEmpty ? MascaradeTheme.rule : tone.opacity(0.4), lineWidth: 1)
                            }
                    }
                    .padding(.horizontal, 20)

                    // Statut + Priorité côte à côte
                    HStack(spacing: 12) {
                        pickerCard(label: "Statut", icon: "circle.dotted") {
                            Picker("", selection: $selectedStatus) {
                                ForEach(FrappeTaskStatus.allCases, id: \.self) { s in
                                    Text(s.label).tag(s)
                                }
                            }
                            .pickerStyle(.menu)
                            .tint(tone)
                        }

                        pickerCard(label: "Priorité", icon: "flag") {
                            Picker("", selection: $selectedPriority) {
                                ForEach(priorities, id: \.self) { p in
                                    Text(p).tag(p)
                                }
                            }
                            .pickerStyle(.menu)
                            .tint(MascaradeTheme.amber)
                        }
                    }
                    .padding(.horizontal, 20)

                    // Projet
                    if !projects.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Label("Projet", systemImage: "folder")
                                .font(.system(.caption, design: .rounded).weight(.semibold))
                                .foregroundStyle(MascaradeTheme.muted)
                            Picker("", selection: $selectedProject) {
                                Text("Aucun").tag("")
                                ForEach(projects) { p in
                                    Text(p.projectName.isEmpty ? p.name : p.projectName).tag(p.name)
                                }
                            }
                            .pickerStyle(.menu)
                            .tint(MascaradeTheme.blue)
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(MascaradeTheme.card)
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                            .overlay {
                                RoundedRectangle(cornerRadius: 12, style: .continuous)
                                    .stroke(MascaradeTheme.rule, lineWidth: 1)
                            }
                        }
                        .padding(.horizontal, 20)
                    }

                    // Échéance
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Échéance", systemImage: "calendar")
                            .font(.system(.caption, design: .rounded).weight(.semibold))
                            .foregroundStyle(MascaradeTheme.muted)
                        VStack(spacing: 0) {
                            Toggle(isOn: $showDatePicker) {
                                Text("Définir une date")
                                    .font(.system(.subheadline, design: .rounded))
                                    .foregroundStyle(MascaradeTheme.foreground)
                            }
                            .tint(MascaradeTheme.signal)
                            .padding(12)

                            if showDatePicker {
                                Divider().overlay(MascaradeTheme.rule)
                                DatePicker(
                                    "",
                                    selection: Binding(
                                        get: { expEndDate ?? Date() },
                                        set: { expEndDate = $0 }
                                    ),
                                    displayedComponents: .date
                                )
                                .datePickerStyle(.graphical)
                                .tint(MascaradeTheme.signal)
                                .padding(8)
                                .onAppear { if expEndDate == nil { expEndDate = Date() } }
                            }
                        }
                        .background(MascaradeTheme.card)
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .overlay {
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .stroke(MascaradeTheme.rule, lineWidth: 1)
                        }
                    }
                    .padding(.horizontal, 20)

                    // Description
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Description", systemImage: "text.alignleft")
                            .font(.system(.caption, design: .rounded).weight(.semibold))
                            .foregroundStyle(MascaradeTheme.muted)
                        TextField("Notes, contexte, détails…", text: $taskDescription, axis: .vertical)
                            .font(.system(.callout, design: .rounded))
                            .lineLimit(3...8)
                            .padding(12)
                            .background(MascaradeTheme.card)
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                            .overlay {
                                RoundedRectangle(cornerRadius: 12, style: .continuous)
                                    .stroke(MascaradeTheme.rule, lineWidth: 1)
                            }
                    }
                    .padding(.horizontal, 20)

                    // Erreur
                    if let errorMessage {
                        HStack(spacing: 8) {
                            Image(systemName: "exclamationmark.triangle.fill")
                            Text(errorMessage)
                                .font(.system(.footnote, design: .rounded))
                        }
                        .foregroundStyle(MascaradeTheme.error)
                        .padding(12)
                        .background(MascaradeTheme.error.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                        .padding(.horizontal, 20)
                    }

                    // Bouton créer
                    Button {
                        Task { await save() }
                    } label: {
                        HStack(spacing: 8) {
                            if isSaving {
                                ProgressView().progressViewStyle(.circular).tint(.white).scaleEffect(0.8)
                            } else {
                                Image(systemName: "plus.circle.fill")
                            }
                            Text(isSaving ? "Création…" : "Créer la tâche")
                                .font(.system(.body, design: .rounded).weight(.semibold))
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(canSave ? MascaradeTheme.signal : MascaradeTheme.muted.opacity(0.4))
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                    .disabled(!canSave)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 32)
                }
                .padding(.top, 8)
            }
            .background(MascaradeTheme.card.opacity(0.5))
            .navigationTitle("Nouvelle tâche")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Annuler") { dismiss() }
                        .foregroundStyle(MascaradeTheme.muted)
                }
            }
        }
    }

    @ViewBuilder
    private func pickerCard<Content: View>(
        label: String,
        icon: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(label, systemImage: icon)
                .font(.system(.caption, design: .rounded).weight(.semibold))
                .foregroundStyle(MascaradeTheme.muted)
            content()
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(MascaradeTheme.card)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .stroke(MascaradeTheme.rule, lineWidth: 1)
                }
        }
        .frame(maxWidth: .infinity)
    }

    private func save() async {
        let trimmed = subject.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        guard let baseURL = frappeSettings.resolvedBaseURL() else {
            errorMessage = "URL Frappe non configurée."
            return
        }

        isSaving = true
        errorMessage = nil

        let client = FrappeAPI(baseURL: baseURL, authHeader: frappeSettings.authorizationHeader)
        let dueDateStr = showDatePicker ? expEndDate.map { dateFormatter.string(from: $0) } : nil

        do {
            try await client.createTask(
                subject: trimmed,
                status: selectedStatus.rawValue,
                priority: selectedPriority,
                project: selectedProject.isEmpty ? nil : selectedProject,
                description: taskDescription.isEmpty ? nil : taskDescription,
                expEndDate: dueDateStr
            )
            await onCreated()
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
            isSaving = false
        }
    }
}

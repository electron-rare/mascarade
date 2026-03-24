//
//  ViewComponents.swift
//  Mascarade
//
//  Shared UI primitives, helper structs, button styles, and extensions
//  extracted from ContentView.swift.
//

import SwiftUI

// MARK: - Data models

struct HeaderMetric: Identifiable {
    let label: String
    let value: String
    let note: String

    var id: String {
        "\(label)-\(value)-\(note)"
    }
}

struct ExhibitRoute: Identifiable {
    let id = UUID()
    let title: String
    let eyebrow: String
    let subtitle: String
    let accent: Color
    let facts: [HeaderMetric]
    let notes: [String]
}

// MARK: - Card components

struct HeroCard: View {
    let title: String
    let mode: CabinetMode
    let message: String
    let manifesto: String
    let metrics: [HeaderMetric]
    @ObservedObject var settings: ConnectionSettings
    @ObservedObject var viewModel: CockpitViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            HStack(alignment: .top, spacing: 22) {
                VStack(alignment: .leading, spacing: 14) {
                    TapeLabel(text: mode.bannerText, tone: mode.accent, dark: true)

                    Text(title)
                        .font(.system(size: 56, weight: .regular, design: .serif))
                        .tracking(-1.6)
                        .foregroundStyle(MascaradeTheme.invertedForeground)

                    Text(message)
                        .font(.system(.title3, design: .rounded))
                        .foregroundStyle(MascaradeTheme.invertedForeground.opacity(0.9))
                        .fixedSize(horizontal: false, vertical: true)

                    Text(manifesto)
                        .font(.system(.footnote, design: .monospaced))
                        .foregroundStyle(MascaradeTheme.heroMuted)
                        .padding(.top, 4)

                    HStack(spacing: 10) {
                        CapsuleLabel(
                            text: settings.normalizedBaseURL.isEmpty ? "URL missing" : settings.normalizedBaseURL,
                            tone: MascaradeTheme.signal,
                            foreground: MascaradeTheme.invertedForeground
                        )
                        CapsuleLabel(
                            text: settings.apiKey.isEmpty ? "open dev mode" : "bearer auth",
                            tone: MascaradeTheme.amber,
                            foreground: MascaradeTheme.invertedForeground
                        )
                        CapsuleLabel(
                            text: viewModel.lastRefreshLabel,
                            tone: mode.accent,
                            foreground: MascaradeTheme.invertedForeground
                        )
                    }
                }

                Spacer(minLength: 16)

                VStack(spacing: 12) {
                    ForEach(metrics) { metric in
                        HeroMetricTile(metric: metric, accent: mode.accent)
                    }
                }
                .frame(maxWidth: 280)
            }
        }
        .padding(28)
        .background(
            RoundedRectangle(cornerRadius: 34, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [
                            MascaradeTheme.inkPanel,
                            MascaradeTheme.inkPanelSoft,
                            MascaradeTheme.inkBlue,
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 34, style: .continuous)
                        .stroke(mode.accent.opacity(0.35), lineWidth: 1.2)
                )
                .overlay(alignment: .topTrailing) {
                    Circle()
                        .fill(mode.accent.opacity(0.17))
                        .frame(width: 220, height: 220)
                        .blur(radius: 10)
                        .offset(x: 52, y: -56)
                }
        )
        .shadow(color: Color.black.opacity(0.16), radius: 26, x: 0, y: 18)
    }
}

struct CabinetArenaCard: View {
    let mode: CabinetMode
    let score: Int
    let heat: Int
    let services: [ServiceSnapshot]
    let activeRuns: Int
    let alerts: Int
    let collageSeed: Int

    var body: some View {
        SectionCard(title: "Cabinet du hasard", eyebrow: mode.title, tilt: deterministicAngle(for: mode.rawValue, seed: collageSeed, amplitude: 1.2), accent: mode.accent) {
            TimelineView(.animation(minimumInterval: 0.3)) { timeline in
                let time = timeline.date.timeIntervalSinceReferenceDate

                VStack(spacing: 18) {
                    ZStack {
                        ForEach(0..<3, id: \.self) { ring in
                            Circle()
                                .stroke(
                                    (ring == 1 ? mode.accent : MascaradeTheme.rule).opacity(0.28),
                                    style: StrokeStyle(lineWidth: ring == 1 ? 2 : 1, dash: ring == 1 ? [8, 10] : [])
                                )
                                .frame(width: CGFloat(110 + (ring * 52)), height: CGFloat(110 + (ring * 52)))
                        }

                        ForEach(Array(services.prefix(8).enumerated()), id: \.offset) { index, service in
                            let orbit = CGFloat(62 + (index % 4) * 30)
                            let angle = time * (service.ok ? 0.8 : 0.45) + Double(index) * 0.9 + Double(collageSeed)
                            let x = cos(angle) * orbit
                            let y = sin(angle) * orbit * 0.72

                            Circle()
                                .fill(service.ok ? MascaradeTheme.success : MascaradeTheme.error)
                                .frame(width: service.ok ? 12 : 15, height: service.ok ? 12 : 15)
                                .overlay(
                                    Circle()
                                        .stroke(Color.white.opacity(0.25), lineWidth: 1)
                                )
                                .shadow(color: (service.ok ? MascaradeTheme.success : MascaradeTheme.error).opacity(0.42), radius: 10)
                                .offset(x: x, y: y)
                        }

                        VStack(spacing: 6) {
                            Text("\(score)")
                                .font(.system(size: 58, weight: .regular, design: .serif))
                                .foregroundStyle(MascaradeTheme.foreground)

                            Text("score du cabinet")
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(MascaradeTheme.muted)
                        }
                        .padding(26)
                        .background(MascaradeTheme.card.opacity(0.72))
                        .overlay(
                            Circle()
                                .stroke(mode.accent.opacity(0.35), lineWidth: 1.2)
                        )
                        .clipShape(Circle())
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)

                    HStack(spacing: 10) {
                        SnapshotTile(metric: HeaderMetric(label: "Heat", value: "\(heat)", note: "fievre"), dark: false)
                        SnapshotTile(metric: HeaderMetric(label: "Runs", value: "\(activeRuns)", note: "actifs"), dark: false)
                        SnapshotTile(metric: HeaderMetric(label: "Alerts", value: "\(alerts)", note: "epingles"), dark: false)
                    }
                }
            }
            .frame(maxWidth: .infinity)
        }
    }
}

struct DadaControlDeck: View {
    let mode: CabinetMode
    let agent: AgentSummary?
    let workflow: WorkflowSummary?
    let missionLine: String
    @ObservedObject var settings: ConnectionSettings
    @ObservedObject var viewModel: CockpitViewModel
    let onRefresh: () -> Void
    let onShuffle: () -> Void
    let onOpenAgents: () -> Void
    let onOpenWorkflows: () -> Void
    let onOpenAgentExhibit: () -> Void
    let onOpenWorkflowExhibit: () -> Void

    var body: some View {
        SectionCard(title: "Bureau des commandes absurdes", eyebrow: "action deck", tilt: -1.4, accent: mode.accent) {
            Text(missionLine)
                .font(.system(.body, design: .rounded))
                .foregroundStyle(MascaradeTheme.foreground)

            HStack(spacing: 10) {
                Button {
                    onRefresh()
                } label: {
                    DadaActionButtonLabel(icon: "arrow.clockwise", title: "Secouer", subtitle: "relancer")
                }
                .buttonStyle(ActionDeckButtonStyle(accent: mode.accent))

                Button {
                    onShuffle()
                } label: {
                    DadaActionButtonLabel(icon: "shuffle", title: "Battre", subtitle: "hasard")
                }
                .buttonStyle(ActionDeckButtonStyle(accent: MascaradeTheme.blue))
            }

            HStack(spacing: 10) {
                Button {
                    onOpenAgents()
                } label: {
                    DadaActionButtonLabel(icon: "person.2", title: "Agent", subtitle: agent?.name ?? "aucun")
                }
                .buttonStyle(ActionDeckButtonStyle(accent: MascaradeTheme.success))

                Button {
                    onOpenWorkflows()
                } label: {
                    DadaActionButtonLabel(icon: "waveform.path.ecg.rectangle", title: "Lane", subtitle: workflow?.title ?? "aucune")
                }
                .buttonStyle(ActionDeckButtonStyle(accent: MascaradeTheme.signal))
            }

            ViewThatFits(in: .vertical) {
                HStack(alignment: .top, spacing: 10) {
                    Button {
                        onOpenAgentExhibit()
                    } label: {
                        SpotlightCard(
                            eyebrow: "agent tire",
                            title: agent?.name ?? "Personne",
                            bodyText: agent == nil ? "La chaise reste vide." : "\(agent?.description ?? "")."
                        )
                    }
                    .buttonStyle(.plain)

                    Button {
                        onOpenWorkflowExhibit()
                    } label: {
                        SpotlightCard(
                            eyebrow: "lane tiree",
                            title: workflow?.title ?? "Aucune lane",
                            bodyText: workflow == nil ? "Le theatre est clos." : "\(workflow?.category ?? "categorie muette") | \(workflow?.executionModes.joined(separator: ", ") ?? "sans mode")."
                        )
                    }
                    .buttonStyle(.plain)
                }

                VStack(spacing: 10) {
                    Button {
                        onOpenAgentExhibit()
                    } label: {
                        SpotlightCard(
                            eyebrow: "agent tire",
                            title: agent?.name ?? "Personne",
                            bodyText: agent == nil ? "La chaise reste vide." : "\(agent?.description ?? "")."
                        )
                    }
                    .buttonStyle(.plain)

                    Button {
                        onOpenWorkflowExhibit()
                    } label: {
                        SpotlightCard(
                            eyebrow: "lane tiree",
                            title: workflow?.title ?? "Aucune lane",
                            bodyText: workflow == nil ? "Le theatre est clos." : "\(workflow?.category ?? "categorie muette") | \(workflow?.executionModes.joined(separator: ", ") ?? "sans mode")."
                        )
                    }
                    .buttonStyle(.plain)
                }
            }

            HStack(spacing: 8) {
                CapsuleLabel(text: mode.title.lowercased(), tone: mode.accent)
                CapsuleLabel(text: settings.apiKey.isEmpty ? "masque leve" : "masque pose", tone: MascaradeTheme.amber)
                CapsuleLabel(text: viewModel.apiIsHealthy ? "facade calme" : "facade nerveuse", tone: viewModel.apiIsHealthy ? MascaradeTheme.success : MascaradeTheme.error)
            }
        }
    }
}

struct CollectionHeader: View {
    let eyebrow: String
    let title: String
    let message: String
    let metrics: [HeaderMetric]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            TapeLabel(text: eyebrow, tone: MascaradeTheme.blue)

            Text(title)
                .font(.system(size: 42, weight: .regular, design: .serif))
                .tracking(-0.8)
                .foregroundStyle(MascaradeTheme.foreground)

            Text(message)
                .font(.system(.body, design: .rounded))
                .foregroundStyle(MascaradeTheme.foreground.opacity(0.84))

            SnapshotBand(items: metrics)
        }
        .padding(24)
        .background(MascaradeTheme.card)
        .overlay(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .stroke(MascaradeTheme.rule, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 30, style: .continuous))
        .rotationEffect(.degrees(-0.6))
        .shadow(color: MascaradeTheme.shadow, radius: 18, x: 0, y: 10)
    }
}

struct HeroMetricTile: View {
    let metric: HeaderMetric
    let accent: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(metric.label.uppercased())
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(MascaradeTheme.heroMuted)

            Text(metric.value)
                .font(.system(size: 28, weight: .regular, design: .serif))
                .foregroundStyle(MascaradeTheme.invertedForeground)
                .lineLimit(1)
                .minimumScaleFactor(0.72)

            Text(metric.note)
                .font(.system(.caption, design: .rounded))
                .foregroundStyle(MascaradeTheme.invertedForeground.opacity(0.74))
                .lineLimit(2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(MascaradeTheme.heroPanel)
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(accent.opacity(0.35), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
    }
}

struct SnapshotBand: View {
    let items: [HeaderMetric]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 12) {
                ForEach(items) { item in
                    SnapshotTile(metric: item, dark: false)
                }
            }
            .padding(.vertical, 2)
        }
    }
}

struct SnapshotTile: View {
    let metric: HeaderMetric
    let dark: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(metric.label.uppercased())
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(dark ? MascaradeTheme.heroMuted : MascaradeTheme.muted)

            Text(metric.value)
                .font(.system(size: 24, weight: .regular, design: .serif))
                .foregroundStyle(dark ? MascaradeTheme.invertedForeground : MascaradeTheme.foreground)
                .lineLimit(1)
                .minimumScaleFactor(0.68)

            Text(metric.note)
                .font(.system(.caption, design: .rounded))
                .foregroundStyle(dark ? MascaradeTheme.invertedForeground.opacity(0.7) : MascaradeTheme.muted)
                .lineLimit(2)
        }
        .frame(width: 180, alignment: .leading)
        .padding(16)
        .background(dark ? MascaradeTheme.heroPanel : MascaradeTheme.panel)
        .overlay(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(dark ? MascaradeTheme.heroRule : MascaradeTheme.rule, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
    }
}

struct SectionCard<Content: View>: View {
    let title: String
    let eyebrow: String?
    let tilt: Double
    let accent: Color
    let content: Content

    init(
        title: String,
        eyebrow: String? = nil,
        tilt: Double = 0,
        accent: Color = MascaradeTheme.rule,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.eyebrow = eyebrow
        self.tilt = tilt
        self.accent = accent
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            if let eyebrow, !eyebrow.isEmpty {
                TapeLabel(text: eyebrow, tone: accent)
            }

            Text(title)
                .font(.system(size: 24, weight: .medium, design: .serif))
                .foregroundStyle(MascaradeTheme.foreground)

            Rectangle()
                .fill(MascaradeTheme.rule)
                .frame(height: 1)

            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(22)
        .background(MascaradeTheme.card)
        .overlay(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(accent.opacity(0.4), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .rotationEffect(.degrees(tilt))
        .shadow(color: MascaradeTheme.shadow, radius: 18, x: 0, y: 10)
    }
}

struct TapeLabel: View {
    let text: String
    let tone: Color
    var dark = false

    var body: some View {
        Text(text.uppercased())
            .font(.system(.caption, design: .monospaced))
            .foregroundStyle(dark ? MascaradeTheme.invertedForeground : MascaradeTheme.foreground)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(tone.opacity(dark ? 0.18 : 0.16))
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(tone.opacity(0.5), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            .rotationEffect(.degrees(-3.2))
    }
}

struct SpotlightCard: View {
    let eyebrow: String
    let title: String
    let bodyText: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            TapeLabel(text: eyebrow, tone: MascaradeTheme.panelBorder)

            Text(title)
                .font(.system(size: 22, weight: .medium, design: .serif))
                .foregroundStyle(MascaradeTheme.foreground)

            Text(bodyText)
                .font(.system(.footnote, design: .rounded))
                .foregroundStyle(MascaradeTheme.foreground.opacity(0.78))
                .lineLimit(4)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(MascaradeTheme.panel)
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(MascaradeTheme.rule, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

struct WorkflowDeckCard: View {
    let workflow: WorkflowSummary
    let selected: Bool
    let tilt: Double

    var body: some View {
        SectionCard(
            title: workflow.title,
            eyebrow: workflow.category,
            tilt: tilt,
            accent: selected ? MascaradeTheme.signal : MascaradeTheme.rule
        ) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("v\(workflow.version) | \(workflow.nodeCount) nodes | \(workflow.edgeCount) edges")
                        .font(.system(.subheadline, design: .monospaced))
                        .foregroundStyle(MascaradeTheme.foreground)
                        .textSelection(.enabled)

                    Text("Updated \(relativeTime(from: workflow.updatedAt))")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(MascaradeTheme.muted)
                }

                Spacer()

                StatusIndicator(
                    ok: workflow.latestRun?.status == "success",
                    label: workflow.latestRun?.status.uppercased() ?? workflow.status.uppercased()
                )
            }

            if !workflow.tags.isEmpty {
                FlowRow(items: workflow.tags, tone: MascaradeTheme.amber)
            }

            HStack(spacing: 8) {
                ForEach(workflow.executionModes, id: \.self) { mode in
                    CapsuleLabel(text: mode, tone: MascaradeTheme.blue)
                }
            }

            if selected {
                ArtifactNote(
                    text: "\(workflow.title) se joue en \(workflow.executionModes.joined(separator: ", ")) et renverse \(workflow.nodeCount) noeuds comme un decor portatif."
                )
                .transition(.collageShard)
            }

            if let latestRun = workflow.latestRun {
                Text("Run \(latestRun.runId)")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(MascaradeTheme.muted)
                    .textSelection(.enabled)
            }
        }
        .scaleEffect(selected ? 1.015 : 1)
    }
}

struct ReceiptTicketView: View {
    let mode: CabinetMode
    let score: Int
    let heat: Int
    let endpoint: String
    let agentName: String
    let workflowTitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("CABINET RECEIPT")
                Spacer()
                Text(mode.title.uppercased())
            }
            .font(.system(.caption, design: .monospaced))
            .foregroundStyle(MascaradeTheme.ticketInk)

            Rectangle()
                .fill(MascaradeTheme.ticketInk.opacity(0.28))
                .frame(height: 1)

            ReceiptLine(label: "SCORE", value: "\(score)")
            ReceiptLine(label: "HEAT", value: "\(heat)")
            ReceiptLine(label: "AGENT", value: agentName)
            ReceiptLine(label: "LANE", value: workflowTitle)
            ReceiptLine(label: "URL", value: endpoint.isEmpty ? "not set" : endpoint)

            Rectangle()
                .fill(MascaradeTheme.ticketInk.opacity(0.28))
                .frame(height: 1)

            Text("tire la languette ou entre dans la salle")
                .font(.system(.footnote, design: .monospaced))
                .foregroundStyle(MascaradeTheme.ticketInk.opacity(0.78))
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 16)
        .background(MascaradeTheme.ticketPaper)
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(MascaradeTheme.ticketInk.opacity(0.24), style: StrokeStyle(lineWidth: 1, dash: [6, 5]))
        )
        .overlay(alignment: .leading) {
            TicketPerforation()
                .offset(x: -9)
        }
        .overlay(alignment: .trailing) {
            TicketPerforation()
                .offset(x: 9)
        }
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .rotationEffect(.degrees(-1.2))
        .shadow(color: MascaradeTheme.shadow, radius: 12, x: 0, y: 8)
    }
}

struct ReceiptLine: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(MascaradeTheme.ticketInk.opacity(0.72))
            Spacer(minLength: 12)
            Text(value)
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(MascaradeTheme.ticketInk)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
    }
}

struct TicketPerforation: View {
    var body: some View {
        VStack(spacing: 10) {
            ForEach(0..<6, id: \.self) { _ in
                Circle()
                    .fill(MascaradeTheme.ticketShadow)
                    .frame(width: 10, height: 10)
            }
        }
    }
}

struct ExhibitHallView: View {
    let exhibit: ExhibitRoute
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    MascaradeTheme.inkPanel,
                    MascaradeTheme.inkBlue,
                    MascaradeTheme.inkPanelSoft,
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    SectionCard(title: exhibit.title, eyebrow: exhibit.eyebrow, tilt: -1.4, accent: exhibit.accent) {
                        Text(exhibit.subtitle)
                            .font(.system(.title3, design: .rounded))
                            .foregroundStyle(MascaradeTheme.foreground)

                        SnapshotBand(items: exhibit.facts)

                        ForEach(Array(exhibit.notes.enumerated()), id: \.offset) { index, note in
                            ArtifactNote(text: note)
                                .rotationEffect(.degrees(index.isMultiple(of: 2) ? -0.7 : 0.9))
                                .transition(.collageShard)
                        }
                    }

                    ReceiptTicketView(
                        mode: .hasard,
                        score: Int(exhibit.facts.first?.value ?? "0") ?? 0,
                        heat: Int(exhibit.facts.dropFirst().first?.value ?? "0") ?? 0,
                        endpoint: exhibit.eyebrow,
                        agentName: exhibit.title,
                        workflowTitle: exhibit.subtitle
                    )

                    MarqueeTape(text: "\(exhibit.eyebrow)   //   \(exhibit.title)   //   exposition interactive   //   tap to leave")
                }
                .padding(.horizontal, 20)
                .padding(.top, 80)
                .padding(.bottom, 24)
            }

            VStack {
                HStack {
                    Spacer()
                    Button {
                        dismiss()
                    } label: {
                        Label("Quitter", systemImage: "xmark")
                    }
                    .buttonStyle(ActionDeckButtonStyle(accent: exhibit.accent))
                }
                .padding(.horizontal, 20)
                .padding(.top, 18)

                Spacer()
            }
        }
    }
}

// MARK: - Small display primitives

struct DadaActionButtonLabel: View {
    let icon: String
    let title: String
    let subtitle: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 18, weight: .medium))

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(.subheadline, design: .monospaced))
                Text(subtitle)
                    .font(.system(.caption, design: .rounded))
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct StatusRow: View {
    let label: String
    let detail: String
    let ok: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            StatusIndicator(ok: ok, label: "")

            VStack(alignment: .leading, spacing: 4) {
                Text(label)
                    .font(.system(.headline, design: .rounded))
                    .foregroundStyle(MascaradeTheme.foreground)
                Text(detail)
                    .font(.system(.footnote, design: .monospaced))
                    .foregroundStyle(MascaradeTheme.muted)
                    .textSelection(.enabled)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct MetricRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(.system(.subheadline, design: .monospaced))
                .foregroundStyle(MascaradeTheme.muted)
            Spacer()
            Text(value)
                .font(.system(.subheadline, design: .rounded))
                .foregroundStyle(MascaradeTheme.foreground)
                .textSelection(.enabled)
        }
    }
}

struct RunCard: View {
    let run: RecentRun

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(run.message)
                        .font(.system(.body, design: .rounded))
                        .foregroundStyle(MascaradeTheme.foreground)

                    Text(run.runId)
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(MascaradeTheme.muted)
                        .textSelection(.enabled)
                }

                Spacer()

                Text(relativeTime(from: run.ts))
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(MascaradeTheme.muted)
            }

            HStack(spacing: 8) {
                CapsuleLabel(text: run.mode.uppercased(), tone: MascaradeTheme.signal)
                if let agentName = run.agentName, !agentName.isEmpty {
                    CapsuleLabel(text: agentName, tone: MascaradeTheme.success)
                }
                CapsuleLabel(text: run.eventType, tone: MascaradeTheme.panelBorder)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(MascaradeTheme.panel)
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(MascaradeTheme.rule, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

struct AlertRow: View {
    let alert: AlertEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                CapsuleLabel(text: alert.severity.uppercased(), tone: severityTone(alert.severity))
                if let service = alert.service, !service.isEmpty {
                    CapsuleLabel(text: service, tone: MascaradeTheme.panelBorder)
                }
                Spacer()
                Text(relativeTime(from: alert.ts))
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(MascaradeTheme.muted)
            }

            Text(alert.message)
                .font(.system(.body, design: .rounded))
                .foregroundStyle(MascaradeTheme.foreground)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(MascaradeTheme.panel)
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(MascaradeTheme.rule, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private func severityTone(_ value: String) -> Color {
        switch value {
        case "critical", "error":
            return MascaradeTheme.error
        case "warning":
            return MascaradeTheme.amber
        default:
            return MascaradeTheme.success
        }
    }
}

struct ArtifactNote: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(.footnote, design: .rounded))
            .foregroundStyle(MascaradeTheme.foreground.opacity(0.82))
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(MascaradeTheme.panel)
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(MascaradeTheme.rule, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

struct EmptyLane: View {
    let message: String

    var body: some View {
        Text(message)
            .font(.system(.body, design: .rounded))
            .foregroundStyle(MascaradeTheme.muted)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .background(MascaradeTheme.panel)
            .overlay(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .stroke(MascaradeTheme.rule, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

struct BannerView: View {
    let message: String
    let tone: Color

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "sparkle.magnifyingglass")
                .foregroundStyle(tone)

            Text(message)
                .font(.system(.subheadline, design: .rounded))
                .foregroundStyle(MascaradeTheme.foreground)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(
            LinearGradient(
                colors: [
                    MascaradeTheme.panel,
                    MascaradeTheme.card,
                ],
                startPoint: .leading,
                endPoint: .trailing
            )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(tone.opacity(0.42), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .shadow(color: MascaradeTheme.shadow, radius: 10, x: 0, y: 6)
    }
}

struct MarqueeTape: View {
    let text: String

    var body: some View {
        TimelineView(.animation(minimumInterval: 1 / 30)) { timeline in
            GeometryReader { proxy in
                let cycle = proxy.size.width + 260
                let progress = timeline.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 12) / 12

                HStack(spacing: 28) {
                    ForEach(0..<6, id: \.self) { _ in
                        Text(text.uppercased())
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(MascaradeTheme.foreground)
                    }
                }
                .offset(x: -CGFloat(progress) * cycle)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .frame(height: 42)
        .padding(.horizontal, 14)
        .background(MascaradeTheme.paperTape)
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(MascaradeTheme.rule, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .rotationEffect(.degrees(0.5))
    }
}

struct StatusIndicator: View {
    let ok: Bool
    let label: String

    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(ok ? MascaradeTheme.success : MascaradeTheme.error)
                .frame(width: 10, height: 10)
                .shadow(color: (ok ? MascaradeTheme.success : MascaradeTheme.error).opacity(0.32), radius: 6)

            if !label.isEmpty {
                Text(label)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(ok ? MascaradeTheme.success : MascaradeTheme.error)
            }
        }
    }
}

struct CapsuleLabel: View {
    let text: String
    let tone: Color
    var foreground = MascaradeTheme.foreground

    var body: some View {
        Text(text)
            .font(.system(.caption, design: .monospaced))
            .lineLimit(1)
            .minimumScaleFactor(0.72)
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(tone.opacity(0.12))
            .overlay(
                Capsule()
                    .stroke(tone.opacity(0.42), lineWidth: 1)
            )
            .clipShape(Capsule())
            .foregroundStyle(foreground)
    }
}

struct RefreshButton: View {
    @ObservedObject var viewModel: CockpitViewModel
    @ObservedObject var settings: ConnectionSettings

    var body: some View {
        Button {
            Task {
                await viewModel.refresh(using: settings)
            }
        } label: {
            Group {
                if viewModel.isRefreshing {
                    ProgressView()
                        .tint(MascaradeTheme.signal)
                } else {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
            }
        }
        .buttonStyle(PrimaryButtonStyle())
    }
}

struct FlowRow: View {
    let items: [String]
    let tone: Color

    var body: some View {
        ViewThatFits(in: .vertical) {
            HStack(spacing: 8) {
                ForEach(items, id: \.self) { item in
                    CapsuleLabel(text: item, tone: tone)
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                ForEach(items, id: \.self) { item in
                    CapsuleLabel(text: item, tone: tone)
                }
            }
        }
    }
}

struct MascaradeBackdrop: View {
    var body: some View {
        GeometryReader { proxy in
            ZStack {
                LinearGradient(
                    colors: [
                        Color(red: 0.97, green: 0.94, blue: 0.90),
                        Color(red: 0.92, green: 0.88, blue: 0.82),
                        Color(red: 0.98, green: 0.96, blue: 0.92),
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )

                Circle()
                    .fill(MascaradeTheme.blue.opacity(0.14))
                    .frame(width: max(proxy.size.width * 0.76, 520), height: max(proxy.size.width * 0.76, 520))
                    .blur(radius: 34)
                    .offset(x: proxy.size.width * 0.26, y: -proxy.size.height * 0.24)

                Circle()
                    .fill(MascaradeTheme.signal.opacity(0.18))
                    .frame(width: max(proxy.size.width * 0.48, 320), height: max(proxy.size.width * 0.48, 320))
                    .blur(radius: 24)
                    .offset(x: -proxy.size.width * 0.28, y: proxy.size.height * 0.26)

                RoundedRectangle(cornerRadius: 56, style: .continuous)
                    .stroke(MascaradeTheme.rule.opacity(0.35), lineWidth: 1)
                    .frame(width: min(proxy.size.width * 0.88, 760), height: min(proxy.size.height * 0.44, 360))
                    .rotationEffect(.degrees(-8))
                    .offset(x: proxy.size.width * 0.13, y: -proxy.size.height * 0.12)

                RoundedRectangle(cornerRadius: 42, style: .continuous)
                    .fill(Color.white.opacity(0.18))
                    .frame(width: min(proxy.size.width * 0.44, 360), height: min(proxy.size.height * 0.24, 220))
                    .blur(radius: 3)
                    .rotationEffect(.degrees(9))
                    .offset(x: -proxy.size.width * 0.16, y: proxy.size.height * 0.25)

                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(MascaradeTheme.paperTape)
                    .frame(width: 180, height: 36)
                    .rotationEffect(.degrees(-13))
                    .offset(x: proxy.size.width * 0.29, y: proxy.size.height * 0.16)
                    .blur(radius: 0.2)
            }
        }
    }
}

// MARK: - Button styles

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(.subheadline, design: .monospaced))
            .padding(.horizontal, 16)
            .padding(.vertical, 11)
            .background(MascaradeTheme.signal.opacity(configuration.isPressed ? 0.24 : 0.16))
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .stroke(MascaradeTheme.signal.opacity(0.5), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .foregroundStyle(MascaradeTheme.foreground)
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(.subheadline, design: .monospaced))
            .padding(.horizontal, 16)
            .padding(.vertical, 11)
            .background(MascaradeTheme.panel.opacity(configuration.isPressed ? 0.92 : 1))
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .stroke(MascaradeTheme.rule, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .foregroundStyle(MascaradeTheme.foreground)
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
    }
}

struct ActionDeckButtonStyle: ButtonStyle {
    let accent: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(accent.opacity(configuration.isPressed ? 0.24 : 0.14))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(accent.opacity(0.5), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .foregroundStyle(MascaradeTheme.foreground)
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
    }
}

// MARK: - Geometry effects

struct ShakeEffect: GeometryEffect {
    var amount: CGFloat = 9
    var shakesPerUnit: CGFloat = 3
    var animatableData: CGFloat

    func effectValue(size: CGSize) -> ProjectionTransform {
        ProjectionTransform(
            CGAffineTransform(translationX: amount * sin(animatableData * .pi * shakesPerUnit), y: 0)
        )
    }
}

struct CollageShardModifier: ViewModifier {
    let angle: Double
    let scale: CGFloat
    let offset: CGSize
    let opacity: Double

    func body(content: Content) -> some View {
        content
            .rotationEffect(.degrees(angle))
            .scaleEffect(scale)
            .offset(offset)
            .opacity(opacity)
    }
}

// MARK: - Helper functions

func statusText(_ ok: Bool) -> String {
    ok ? "up" : "down"
}

func latencyLabel(_ value: Double?) -> String {
    guard let value else {
        return "n/a"
    }

    return "\(Int(value.rounded())) ms"
}

func relativeTime(from raw: String) -> String {
    guard let date = ISO8601DateFormatter.mascarade.date(from: raw) else {
        return raw
    }

    return RelativeDateTimeFormatter.mascarade.localizedString(for: date, relativeTo: Date())
}

func deterministicAngle(for key: String, seed: Int, amplitude: Double) -> Double {
    let scalarSum = key.unicodeScalars.reduce(seed * 97) { partialResult, scalar in
        partialResult + Int(scalar.value)
    }
    let normalized = Double(abs(scalarSum % 1000)) / 1000
    return (normalized * amplitude * 2) - amplitude
}

// MARK: - Extensions

extension AnyTransition {
    static var collageShard: AnyTransition {
        .modifier(
            active: CollageShardModifier(
                angle: -12,
                scale: 0.84,
                offset: CGSize(width: -40, height: 28),
                opacity: 0
            ),
            identity: CollageShardModifier(
                angle: 0,
                scale: 1,
                offset: .zero,
                opacity: 1
            )
        )
    }
}

extension ISO8601DateFormatter {
    static let mascarade: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()
}

extension RelativeDateTimeFormatter {
    static let mascarade: RelativeDateTimeFormatter = {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .short
        return formatter
    }()
}

extension ProcessInfo {
    var isRunningForPreviews: Bool {
        environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1"
    }
}

extension View {
    @ViewBuilder
    func exhibitPresentation(exhibit: Binding<ExhibitRoute?>) -> some View {
#if os(macOS)
        sheet(item: exhibit) { route in
            ExhibitHallView(exhibit: route)
                .frame(minWidth: 820, minHeight: 620)
        }
#else
        fullScreenCover(item: exhibit) { route in
            ExhibitHallView(exhibit: route)
        }
#endif
    }

    @ViewBuilder
    func mascaradeTextInput() -> some View {
#if os(iOS) || os(visionOS)
        self
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
#else
        self
#endif
    }
}

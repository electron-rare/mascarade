//
//  DashboardView.swift
//  Mascarade
//
//  Cabinet view (remote cockpit) with arena, control deck, and metrics.
//

import SwiftUI

enum CabinetMode: String, CaseIterable, Identifiable {
    case sabotage
    case parade
    case hasard

    var id: String { rawValue }

    var title: String {
        switch self {
        case .sabotage:
            return "Sabotage"
        case .parade:
            return "Parade"
        case .hasard:
            return "Hasard"
        }
    }

    var subtitle: String {
        switch self {
        case .sabotage:
            return "on pousse les alertes sous la lampe"
        case .parade:
            return "on traite la stack comme une revue vivante"
        case .hasard:
            return "on laisse le systeme tirer ses cartes"
        }
    }

    var accent: Color {
        switch self {
        case .sabotage:
            return MascaradeTheme.error
        case .parade:
            return MascaradeTheme.signal
        case .hasard:
            return MascaradeTheme.blue
        }
    }

    var bannerText: String {
        switch self {
        case .sabotage:
            return "cabinet du sabotage methodique"
        case .parade:
            return "parade mecanique pour machines nerveuses"
        case .hasard:
            return "roulette poeme pour services distribues"
        }
    }
}

struct DashboardView: View {
    @ObservedObject var settings: ConnectionSettings
    @ObservedObject var viewModel: CockpitViewModel
    @Binding var selectedTab: AppTab

    @State private var cabinetMode = CabinetMode.parade
    @State private var spotlightAgentID: String?
    @State private var spotlightWorkflowID: String?
    @State private var collageSeed = 0
    @State private var cabinetDrag = CGSize.zero
    @State private var shakeTick: CGFloat = 0
    @State private var exhibit: ExhibitRoute?

    private let columns = [
        GridItem(.adaptive(minimum: 280), spacing: 18, alignment: .top),
    ]

    private var services: [ServiceSnapshot] {
        viewModel.summary?.monitor.services ?? []
    }

    private var servicesUp: Int {
        services.filter(\.ok).count
    }

    private var spotlightAgent: AgentSummary? {
        guard let spotlightAgentID else {
            return viewModel.agents.first
        }

        return viewModel.agents.first(where: { $0.id == spotlightAgentID }) ?? viewModel.agents.first
    }

    private var spotlightWorkflow: WorkflowSummary? {
        guard let spotlightWorkflowID else {
            return viewModel.workflows.first
        }

        return viewModel.workflows.first(where: { $0.id == spotlightWorkflowID }) ?? viewModel.workflows.first
    }

    private var systemScore: Int {
        let serviceScore = services.isEmpty ? 42 : Int((Double(servicesUp) / Double(max(services.count, 1))) * 55)
        let healthBonus = (viewModel.apiIsHealthy ? 12 : 0) + (viewModel.coreIsHealthy ? 10 : 0)
        let runBonus = min(viewModel.summary?.traces.activeRuns ?? 0, 9) * 3
        let alertPenalty = min(viewModel.summary?.alerts.count ?? 0, 8) * 7
        return max(0, min(99, serviceScore + healthBonus + runBonus - alertPenalty))
    }

    private var heatIndex: Int {
        let failures = services.count - servicesUp
        let alerts = viewModel.summary?.alerts.count ?? 0
        return max(5, min(99, failures * 18 + alerts * 11 + (viewModel.apiIsHealthy ? 0 : 12)))
    }

    private var missionLine: String {
        let agentChunk = spotlightAgent?.name ?? "le mime sans nom"
        let workflowChunk = spotlightWorkflow?.title ?? "le lane invisible"
        let healthChunk = viewModel.apiIsHealthy && viewModel.coreIsHealthy ? "respire" : "grince"

        switch cabinetMode {
        case .sabotage:
            return "\(agentChunk) dissout \(workflowChunk) pendant que le gateway \(healthChunk)."
        case .parade:
            return "\(workflowChunk) desfile sous la pluie, \(agentChunk) tient la cadence."
        case .hasard:
            return "\(agentChunk) pioche \(workflowChunk) et le cluster \(healthChunk) par accident."
        }
    }

    private var heroMetrics: [HeaderMetric] {
        [
            HeaderMetric(label: "Score", value: "\(systemScore)", note: "cabinet"),
            HeaderMetric(label: "Heat", value: "\(heatIndex)", note: "fievre"),
            HeaderMetric(label: "Runs", value: "\(viewModel.summary?.traces.activeRuns ?? 0)", note: "encore vivants"),
        ]
    }

    private var snapshotMetrics: [HeaderMetric] {
        [
            HeaderMetric(
                label: "Endpoint",
                value: viewModel.connectedBaseURL.isEmpty ? (settings.normalizedBaseURL.isEmpty ? "Not set" : settings.normalizedBaseURL) : viewModel.connectedBaseURL,
                note: "facade HTTP"
            ),
            HeaderMetric(
                label: "Services",
                value: "\(servicesUp)/\(services.count)",
                note: services.isEmpty ? "aucune ombre" : "debout"
            ),
            HeaderMetric(
                label: "Alerts",
                value: "\(viewModel.summary?.alerts.count ?? 0)",
                note: "cris recents"
            ),
            HeaderMetric(
                label: "Cluster",
                value: viewModel.summary?.cluster?.role ?? "solo",
                note: viewModel.summary?.cluster?.nodeId ?? "node absent"
            ),
        ]
    }

    var body: some View {
        ScrollView {
            dashboardContent
        }
        .navigationTitle("Cabinet")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                RefreshButton(viewModel: viewModel, settings: settings)
            }
        }
        .refreshable {
            await viewModel.refresh(using: settings)
        }
        .onAppear {
            ensureSpotlights()
        }
        .onChange(of: viewModel.agents.count) { _, _ in
            ensureSpotlights()
        }
        .onChange(of: viewModel.workflows.count) { _, _ in
            ensureSpotlights()
        }
        .exhibitPresentation(exhibit: $exhibit)
    }

    private var dashboardContent: some View {
        VStack(alignment: .leading, spacing: 22) {
            heroSection
            printedTicket
            arenaShowcase
            SnapshotBand(items: snapshotMetrics)

            bannerSection
            metricsGrid
            servicesSection
            alertsSection
            runsSection
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 24)
    }

    private var heroSection: some View {
        Group {
            HeroCard(
                title: "Mascarade",
                mode: cabinetMode,
                message: missionLine,
                manifesto: dadaSentence(),
                metrics: heroMetrics,
                settings: settings,
                viewModel: viewModel
            )

            MascaradeArtworkBanner(
                assetName: "CabinetHero",
                eyebrow: "electron fou",
                title: "Cabinet sous tension",
                detail: "un theatre ops electrique, cabosse, mais encore lisible"
            )

            MarqueeTape(
                text: "\(cabinetMode.bannerText)   //   \(missionLine)   //   score \(systemScore)   //   heat \(heatIndex)"
            )
        }
    }

    private var arenaShowcase: some View {
        ViewThatFits(in: .vertical) {
            HStack(alignment: .top, spacing: 18) {
                arenaCard
                controlDeck
            }

            VStack(spacing: 18) {
                arenaCard
                controlDeck
            }
        }
        .rotationEffect(.degrees(Double(cabinetDrag.width / 42)))
        .offset(x: cabinetDrag.width * 0.06, y: cabinetDrag.height * 0.04)
        .modifier(ShakeEffect(animatableData: shakeTick))
        .simultaneousGesture(cabinetShakeGesture)
    }

    private var arenaCard: some View {
        CabinetArenaCard(
            mode: cabinetMode,
            score: systemScore,
            heat: heatIndex,
            services: services,
            activeRuns: viewModel.summary?.traces.activeRuns ?? 0,
            alerts: viewModel.summary?.alerts.count ?? 0,
            collageSeed: collageSeed
        )
    }

    private var controlDeck: some View {
        DadaControlDeck(
            mode: cabinetMode,
            agent: spotlightAgent,
            workflow: spotlightWorkflow,
            missionLine: missionLine,
            settings: settings,
            viewModel: viewModel,
            onRefresh: {
                Task {
                    await viewModel.refresh(using: settings)
                }
            },
            onShuffle: {
                shuffleCabinet()
            },
            onOpenAgents: {
                withAnimation(.spring(response: 0.38, dampingFraction: 0.85)) {
                    selectedTab = .agents
                }
            },
            onOpenWorkflows: {
                withAnimation(.spring(response: 0.38, dampingFraction: 0.85)) {
                    selectedTab = .workflows
                }
            },
            onOpenAgentExhibit: {
                openAgentExhibit()
            },
            onOpenWorkflowExhibit: {
                openWorkflowExhibit()
            }
        )
    }

    private var printedTicket: some View {
        Button {
            openCabinetExhibit()
        } label: {
            ReceiptTicketView(
                mode: cabinetMode,
                score: systemScore,
                heat: heatIndex,
                endpoint: settings.normalizedBaseURL.isEmpty ? "not set" : settings.normalizedBaseURL,
                agentName: spotlightAgent?.name ?? "aucun",
                workflowTitle: spotlightWorkflow?.title ?? "aucune lane"
            )
        }
        .buttonStyle(.plain)
        .modifier(ShakeEffect(animatableData: shakeTick))
    }

    @ViewBuilder
    private var bannerSection: some View {
        if let message = viewModel.bannerMessage {
            BannerView(message: message, tone: cabinetMode.accent)
                .transition(.collageShard)
        }
    }

    private var metricsGrid: some View {
        LazyVGrid(columns: columns, spacing: 18) {
            SectionCard(title: "Le guichet", eyebrow: "gateway", tilt: cardTilt("gateway")) {
                StatusRow(
                    label: "API",
                    detail: viewModel.health?.status.uppercased() ?? "NO DATA",
                    ok: viewModel.apiIsHealthy
                )
                StatusRow(
                    label: "Core",
                    detail: viewModel.health?.core?.status.uppercased() ?? "NO DATA",
                    ok: viewModel.coreIsHealthy
                )
                StatusRow(
                    label: "URL",
                    detail: viewModel.connectedBaseURL.isEmpty ? settings.normalizedBaseURL : viewModel.connectedBaseURL,
                    ok: !settings.normalizedBaseURL.isEmpty
                )
            }

            SectionCard(title: "Les oracles", eyebrow: "inference", tilt: cardTilt("providers")) {
                StatusRow(
                    label: "Ollama",
                    detail: providerSummary(
                        ok: viewModel.summary?.monitor.ai.ollama.ok,
                        latency: viewModel.summary?.monitor.ai.ollama.latencyMs,
                        suffix: "\(viewModel.summary?.monitor.ai.ollama.models ?? 0) models"
                    ),
                    ok: viewModel.summary?.monitor.ai.ollama.ok ?? false
                )
                StatusRow(
                    label: "Qdrant",
                    detail: providerSummary(
                        ok: viewModel.summary?.monitor.ai.qdrant.ok,
                        latency: viewModel.summary?.monitor.ai.qdrant.latencyMs,
                        suffix: "\(viewModel.summary?.monitor.ai.qdrant.collections ?? 0) collections"
                    ),
                    ok: viewModel.summary?.monitor.ai.qdrant.ok ?? false
                )
                StatusRow(
                    label: "Services",
                    detail: "\(servicesUp)/\(services.count) up",
                    ok: services.isEmpty ? false : servicesUp == services.count
                )
            }

            SectionCard(title: "Le bilan", eyebrow: "operations", tilt: cardTilt("ops")) {
                MetricRow(label: "Agents", value: "\(viewModel.agents.count)")
                MetricRow(label: "Workflows", value: "\(viewModel.workflows.count)")
                MetricRow(label: "Active runs", value: "\(viewModel.summary?.traces.activeRuns ?? 0)")
                MetricRow(label: "Recent alerts", value: "\(viewModel.summary?.alerts.count ?? 0)")
            }

            SectionCard(title: "Le choeur", eyebrow: "cluster", tilt: cardTilt("cluster")) {
                MetricRow(label: "Enabled", value: boolLabel(viewModel.summary?.cluster?.enabled))
                MetricRow(label: "Peers OK", value: clusterPeersLabel(viewModel.summary?.cluster))
                MetricRow(label: "Role", value: viewModel.summary?.cluster?.role ?? "n/a")
                MetricRow(label: "Node", value: viewModel.summary?.cluster?.nodeId ?? "n/a")
            }
        }
    }

    private var servicesSection: some View {
        SectionCard(title: "Les temoins", eyebrow: "observed services", tilt: cardTilt("services")) {
            if services.isEmpty {
                EmptyLane(message: "Aucun service ne remonte encore dans /api/ops/summary.")
            } else {
                ForEach(services) { service in
                    StatusRow(
                        label: service.name,
                        detail: "\(statusText(service.ok)) | \(latencyLabel(service.latencyMs)) | \(service.url)",
                        ok: service.ok
                    )
                }
            }
        }
    }

    private var alertsSection: some View {
        SectionCard(title: "Les cris", eyebrow: "recent alerts", tilt: cardTilt("alerts")) {
            if viewModel.summary?.alerts.isEmpty ?? true {
                EmptyLane(message: "Le cabinet est calme. Aucun cri recent a epingler.")
            } else {
                ForEach(Array((viewModel.summary?.alerts ?? []).prefix(6))) { alert in
                    AlertRow(alert: alert)
                }
            }
        }
    }

    private var runsSection: some View {
        SectionCard(title: "Les traces", eyebrow: "recent runs", tilt: cardTilt("runs")) {
            if viewModel.summary?.traces.recentRuns.isEmpty ?? true {
                EmptyLane(message: "Aucun run recent ne remonte depuis le backend.")
            } else {
                ForEach(Array((viewModel.summary?.traces.recentRuns ?? []).prefix(6))) { run in
                    RunCard(run: run)
                }
            }
        }
    }

    private func ensureSpotlights() {
        if spotlightAgentID == nil {
            spotlightAgentID = viewModel.agents.first?.id
        }

        if spotlightWorkflowID == nil {
            spotlightWorkflowID = viewModel.workflows.first?.id
        }
    }

    private func shuffleCabinet() {
        withAnimation(.spring(response: 0.52, dampingFraction: 0.82)) {
            collageSeed += 1
            let currentIndex = CabinetMode.allCases.firstIndex(of: cabinetMode) ?? 0
            cabinetMode = CabinetMode.allCases[(currentIndex + 1) % CabinetMode.allCases.count]
            spotlightAgentID = viewModel.agents.randomElement()?.id ?? spotlightAgentID
            spotlightWorkflowID = viewModel.workflows.randomElement()?.id ?? spotlightWorkflowID
        }
        triggerShake()
    }

    private var cabinetShakeGesture: some Gesture {
        DragGesture(minimumDistance: 18)
            .onChanged { value in
                cabinetDrag = value.translation
            }
            .onEnded { value in
                let energy = hypot(value.translation.width, value.translation.height)
                withAnimation(.spring(response: 0.35, dampingFraction: 0.88)) {
                    cabinetDrag = .zero
                }
                if energy > 120 {
                    shuffleCabinet()
                }
            }
    }

    private func triggerShake() {
        withAnimation(.linear(duration: 0.45)) {
            shakeTick += 1
        }
    }

    private func openCabinetExhibit() {
        exhibit = ExhibitRoute(
            title: "Cabinet du hasard",
            eyebrow: cabinetMode.bannerText,
            subtitle: missionLine,
            accent: cabinetMode.accent,
            facts: [
                HeaderMetric(label: "Score", value: "\(systemScore)", note: "cabinet"),
                HeaderMetric(label: "Heat", value: "\(heatIndex)", note: "fievre"),
                HeaderMetric(label: "Alerts", value: "\(viewModel.summary?.alerts.count ?? 0)", note: "cris"),
                HeaderMetric(label: "Runs", value: "\(viewModel.summary?.traces.activeRuns ?? 0)", note: "en cours"),
            ],
            notes: [
                dadaSentence(),
                spotlightAgent == nil ? "Aucun agent n'a encore ete tire du paquet." : "\(spotlightAgent?.name ?? "") tient le masque principal.",
                spotlightWorkflow == nil ? "Aucune lane n'est encore montee sur scene." : "\(spotlightWorkflow?.title ?? "") est le decor renverse du moment.",
            ]
        )
    }

    private func openAgentExhibit() {
        guard let spotlightAgent else {
            openCabinetExhibit()
            return
        }

        exhibit = ExhibitRoute(
            title: spotlightAgent.name,
            eyebrow: spotlightAgent.preferredProvider ?? "agent tire",
            subtitle: spotlightAgent.description,
            accent: MascaradeTheme.blue,
            facts: [
                HeaderMetric(label: "Model", value: spotlightAgent.preferredModel ?? "anonyme", note: "visage"),
                HeaderMetric(label: "Role", value: spotlightAgent.preferredRole ?? "muet", note: "posture"),
                HeaderMetric(label: "Strategy", value: spotlightAgent.strategy ?? "aucune", note: "geste"),
                HeaderMetric(label: "Builtin", value: spotlightAgent.builtin ? "yes" : "no", note: "interieur"),
            ],
            notes: [
                "\(spotlightAgent.name) traverse le decor avec \(spotlightAgent.preferredModel ?? "un modele sans etiquette").",
                spotlightAgent.strategy == nil ? "Sa strategie n'a pas encore ete epinglee." : "Sa strategie se note comme \(spotlightAgent.strategy ?? "aucune").",
                missionLine,
            ]
        )
    }

    private func openWorkflowExhibit() {
        guard let spotlightWorkflow else {
            openCabinetExhibit()
            return
        }

        exhibit = ExhibitRoute(
            title: spotlightWorkflow.title,
            eyebrow: spotlightWorkflow.category,
            subtitle: "Version \(spotlightWorkflow.version), \(spotlightWorkflow.nodeCount) noeuds, \(spotlightWorkflow.edgeCount) aretes.",
            accent: MascaradeTheme.signal,
            facts: [
                HeaderMetric(label: "Modes", value: "\(spotlightWorkflow.executionModes.count)", note: "rituels"),
                HeaderMetric(label: "Nodes", value: "\(spotlightWorkflow.nodeCount)", note: "pieces"),
                HeaderMetric(label: "Edges", value: "\(spotlightWorkflow.edgeCount)", note: "fils"),
                HeaderMetric(label: "Status", value: spotlightWorkflow.latestRun?.status ?? spotlightWorkflow.status, note: "etat"),
            ],
            notes: [
                spotlightWorkflow.tags.isEmpty ? "Aucun tag n'est tombe du paquet." : "Etiquettes: \(spotlightWorkflow.tags.joined(separator: ", ")).",
                "La lane se joue en \(spotlightWorkflow.executionModes.joined(separator: ", ")).",
                missionLine,
            ]
        )
    }

    private func dadaSentence() -> String {
        let fragments = [
            settings.normalizedBaseURL.isEmpty ? "l'adresse manque" : "l'adresse se dandine",
            viewModel.apiIsHealthy ? "la facade cligne de l'oeil" : "la facade bafouille",
            viewModel.coreIsHealthy ? "le coeur bat droit" : "le coeur fait des vagues",
            services.isEmpty ? "aucun temoin ne parle" : "\(servicesUp) temoins se tiennent droits",
            (viewModel.summary?.alerts.count ?? 0) == 0 ? "aucun cri n'est epingle" : "\((viewModel.summary?.alerts.count ?? 0)) cris veulent une epingle",
            spotlightWorkflow?.category ?? "la categorie s'efface",
        ]

        let first = fragments[(collageSeed + 1) % fragments.count]
        let second = fragments[(collageSeed + 3) % fragments.count]
        let third = fragments[(collageSeed + 5) % fragments.count]
        return "\(first), \(second), \(third)."
    }

    private func cardTilt(_ key: String) -> Double {
        deterministicAngle(for: key, seed: collageSeed, amplitude: 2.1)
    }

    private func providerSummary(ok: Bool?, latency: Double?, suffix: String) -> String {
        guard let ok else {
            return "no data"
        }

        return "\(statusText(ok)) | \(latencyLabel(latency)) | \(suffix)"
    }

    private func clusterPeersLabel(_ cluster: ClusterSnapshot?) -> String {
        guard let cluster else {
            return "n/a"
        }

        return "\(cluster.peersOk)/\(cluster.peersTotal)"
    }

    private func boolLabel(_ value: Bool?) -> String {
        guard let value else {
            return "n/a"
        }

        return value ? "yes" : "no"
    }
}

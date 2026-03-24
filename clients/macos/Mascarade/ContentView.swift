//
//  ContentView.swift
//  Mascarade
//
//  Root TabView — orchestrates the 5 app tabs.
//  All tab views and shared components live in their own files.
//

import SwiftUI

struct ContentView: View {
    @StateObject private var settings = ConnectionSettings()
    @StateObject private var viewModel = CockpitViewModel()
    @StateObject private var apeSettings = AperantConnectionSettings()
    @StateObject private var frappeSettings = FrappeConnectionSettings()
    @StateObject private var frappeViewModel = FrappeViewModel()
    @StateObject private var frappeRealtime = FrappeRealtimeService()
    @State private var selectedTab = AppTab.cockpit

    var body: some View {
        ZStack {
            MascaradeBackdrop()
                .ignoresSafeArea()

            TabView(selection: $selectedTab) {
                NavigationStack {
                    LocalCockpitView(
                        frappeSettings: frappeSettings,
                        frappeViewModel: frappeViewModel,
                        frappeRealtime: frappeRealtime
                    )
                }
                .tabItem {
                    Label("Cockpit", systemImage: "tray.full")
                }
                .tag(AppTab.cockpit)

                NavigationStack {
                    DashboardView(
                        settings: settings,
                        viewModel: viewModel,
                        selectedTab: $selectedTab
                    )
                }
                .tabItem {
                    Label("Cabinet", systemImage: "sparkles.rectangle.stack")
                }
                .tag(AppTab.monitor)

                NavigationStack {
                    AgentsView(viewModel: viewModel, settings: settings)
                }
                .tabItem {
                    Label("Agents", systemImage: "person.3.sequence")
                }
                .tag(AppTab.agents)

                NavigationStack {
                    ChatView(settings: settings)
                }
                .tabItem {
                    Label("Chat", systemImage: "bubble.left.and.bubble.right")
                }
                .tag(AppTab.chat)

                NavigationStack {
                    MistralBatchView(settings: settings)
                }
                .tabItem {
                    Label("Batch", systemImage: "tray.2")
                }
                .tag(AppTab.batch)

                NavigationStack {
                    WorkflowsView(viewModel: viewModel)
                }
                .tabItem {
                    Label("Lanes", systemImage: "point.3.connected.trianglepath.dotted")
                }
                .tag(AppTab.workflows)

                NavigationStack {
                    AperantView(apeSettings: apeSettings)
                }
                .tabItem {
                    Label("Aperant", systemImage: "cpu.fill")
                }
                .tag(AppTab.aperant)

                NavigationStack {
                    SettingsView(settings: settings, viewModel: viewModel, apeSettings: apeSettings, frappeSettings: frappeSettings)
                }
                .tabItem {
                    Label("Rituel", systemImage: "switch.2")
                }
                .tag(AppTab.settings)
            }
            .tint(MascaradeTheme.signal)
            .animation(.spring(response: 0.42, dampingFraction: 0.88), value: selectedTab)
        }
        .task {
            guard !ProcessInfo.processInfo.isRunningForPreviews else {
                return
            }

            await viewModel.refresh(using: settings)

            // Connexion Socket.io Frappe (push temps réel)
            guard frappeSettings.isConfigured else { return }
            frappeRealtime.onTaskUpdate = {
                Task { await frappeViewModel.refresh(using: frappeSettings, force: true) }
            }
            frappeRealtime.connect(settings: frappeSettings)
        }
    }
}

enum AppTab: Hashable {
    case cockpit
    case monitor
    case agents
    case chat
    case batch
    case workflows
    case aperant
    case settings
}

#Preview {
    ContentView()
        .environment(\.managedObjectContext, PersistenceController.preview.container.viewContext)
        .environmentObject(PersistenceController.preview)
}

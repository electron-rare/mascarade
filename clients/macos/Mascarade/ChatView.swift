//
//  ChatView.swift
//  Mascarade
//
//  Chat interface — sends messages through Mascarade core to any provider.
//

import SwiftUI

struct ChatView: View {
    @ObservedObject var settings: ConnectionSettings
    @State private var inputText = ""
    @State private var messages: [ChatBubble] = []
    @State private var isLoading = false
    @State private var selectedModel = "mistral:mistral-large-latest"
    @State private var errorMessage: String?

    private let availableModels = [
        "mistral:mistral-large-latest",
        "mistral:mistral-small-latest",
        "mistral:codestral-latest",
        "apple-coreml:qwen3-4b-instruct-2507-q4f16",
        "auto",
        "auto:strong",
        "auto:cheap",
        "auto:fast",
    ]

    var body: some View {
        VStack(spacing: 0) {
            // Model picker
            HStack {
                Picker("Model", selection: $selectedModel) {
                    ForEach(availableModels, id: \.self) { model in
                        Text(model).tag(model)
                    }
                }
                .pickerStyle(.menu)
                .frame(maxWidth: 300)

                Spacer()

                if let error = errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .lineLimit(1)
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)

            Divider()

            // Messages
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(messages) { msg in
                            ChatBubbleView(bubble: msg)
                                .id(msg.id)
                        }

                        if isLoading {
                            HStack {
                                ProgressView()
                                    .scaleEffect(0.7)
                                Text("Thinking...")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            .padding(.leading)
                            .id("loading")
                        }
                    }
                    .padding()
                }
                .onChange(of: messages.count) {
                    withAnimation {
                        proxy.scrollTo(messages.last?.id ?? "loading", anchor: .bottom)
                    }
                }
            }

            Divider()

            // Input
            HStack(spacing: 8) {
                TextField("Message...", text: $inputText, axis: .vertical)
                    .textFieldStyle(.plain)
                    .lineLimit(1...5)
                    .onSubmit { send() }

                Button(action: send) {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.title2)
                }
                .buttonStyle(.plain)
                .disabled(inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)
                .keyboardShortcut(.return, modifiers: .command)
            }
            .padding()
        }
        .navigationTitle("Chat")
    }

    private func send() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""
        errorMessage = nil

        messages.append(ChatBubble(role: "user", content: text))

        Task {
            await sendToAPI(text)
        }
    }

    private func sendToAPI(_ text: String) async {
        guard let baseURL = settings.resolvedBaseURL() else {
            errorMessage = "URL non configuree"
            return
        }

        isLoading = true
        defer { isLoading = false }

        let client = MascaradeAPI(baseURL: baseURL, apiKey: settings.apiKey)

        let chatMessages = messages.map { ChatMessage(role: $0.role, content: $0.content) }
        let request = ChatCompletionRequest(
            model: selectedModel,
            messages: chatMessages,
            maxTokens: 1024,
            temperature: 0.7,
            stream: false,
            projectId: "mascarade-app"
        )

        do {
            let response = try await client.post(
                "/v1/chat/completions",
                body: request,
                as: ChatCompletionResponse.self
            )

            if let choice = response.choices.first {
                messages.append(ChatBubble(
                    role: "assistant",
                    content: choice.message.content,
                    model: response.model,
                    tokens: response.usage?.totalTokens
                ))
            }
        } catch {
            errorMessage = error.localizedDescription
            messages.append(ChatBubble(role: "system", content: "Error: \(error.localizedDescription)"))
        }
    }
}

struct ChatBubble: Identifiable {
    let id = UUID()
    let role: String
    let content: String
    var model: String? = nil
    var tokens: Int? = nil
}

struct ChatBubbleView: View {
    let bubble: ChatBubble

    var body: some View {
        HStack {
            if bubble.role == "user" { Spacer(minLength: 60) }

            VStack(alignment: bubble.role == "user" ? .trailing : .leading, spacing: 4) {
                Text(bubble.content)
                    .padding(10)
                    .background(backgroundColor)
                    .foregroundColor(bubble.role == "user" ? .white : .primary)
                    .cornerRadius(12)

                if let model = bubble.model {
                    HStack(spacing: 4) {
                        Text(model)
                        if let tokens = bubble.tokens {
                            Text("(\(tokens) tok)")
                        }
                    }
                    .font(.caption2)
                    .foregroundColor(.secondary)
                }
            }

            if bubble.role != "user" { Spacer(minLength: 60) }
        }
    }

    private var backgroundColor: Color {
        switch bubble.role {
        case "user": return .accentColor
        case "system": return .red.opacity(0.2)
        default: return Color(.controlBackgroundColor)
        }
    }
}

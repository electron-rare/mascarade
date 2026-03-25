import Foundation

@main
struct AFMBridgeMain {
    static func main() async throws {
        var port = 8090

        // Parse --port argument
        let args = CommandLine.arguments
        if let portIndex = args.firstIndex(of: "--port"),
           portIndex + 1 < args.count,
           let parsedPort = Int(args[portIndex + 1]) {
            port = parsedPort
        }

        let server = AFMServer(port: port)
        try await server.run()
    }
}

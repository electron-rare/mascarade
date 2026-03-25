import SwiftUI

struct MascaradeArtworkBanner: View {
    let assetName: String
    let eyebrow: String
    let title: String
    let detail: String
    var height: CGFloat = 188

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            Image(assetName)
                .resizable()
                .scaledToFill()
                .frame(maxWidth: .infinity)
                .frame(height: height)
                .clipped()

            LinearGradient(
                colors: [
                    Color.black.opacity(0.04),
                    Color.black.opacity(0.18),
                    Color.black.opacity(0.68),
                ],
                startPoint: .top,
                endPoint: .bottom
            )

            VStack(alignment: .leading, spacing: 8) {
                Text(eyebrow.uppercased())
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(MascaradeTheme.invertedForeground)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(MascaradeTheme.signal.opacity(0.22))
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(MascaradeTheme.signal.opacity(0.48), lineWidth: 1)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

                Text(title)
                    .font(.system(size: 26, weight: .medium, design: .serif))
                    .foregroundStyle(MascaradeTheme.invertedForeground)

                Text(detail)
                    .font(.system(.footnote, design: .rounded))
                    .foregroundStyle(MascaradeTheme.invertedForeground.opacity(0.88))
                    .lineLimit(2)
            }
            .padding(18)
        }
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(MascaradeTheme.rule.opacity(0.66), lineWidth: 1)
        }
        .shadow(color: Color.black.opacity(0.14), radius: 16, x: 0, y: 10)
    }
}

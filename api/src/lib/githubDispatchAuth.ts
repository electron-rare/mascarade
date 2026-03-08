import { createAppAuth } from "@octokit/auth-app";

export type GitHubDispatchAuthMode = "token" | "app";

export type GitHubDispatchAccessToken = {
  authMode: GitHubDispatchAuthMode;
  token: string;
  expiresAt: string | null;
};

export function normalizeGitHubDispatchAuthMode(
  value: string | undefined | null,
): GitHubDispatchAuthMode {
  return String(value || "").trim().toLowerCase() === "app" ? "app" : "token";
}

export function normalizeGitHubPrivateKey(value: string): string {
  return value.replace(/\r\n/g, "\n").replace(/\\n/g, "\n").trim();
}

export function githubDispatchAppConfigured(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  return Boolean(
    String(env.GITHUB_APP_ID || "").trim() &&
    String(env.GITHUB_APP_PRIVATE_KEY || "").trim() &&
    String(env.GITHUB_APP_INSTALLATION_ID || "").trim(),
  );
}

export function githubDispatchTokenConfigured(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  return Boolean(
    String(env.KILL_LIFE_GITHUB_TOKEN || "").trim() ||
    String(env.GITHUB_TOKEN || "").trim(),
  );
}

export function githubDispatchConfigured(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  return normalizeGitHubDispatchAuthMode(env.GITHUB_DISPATCH_AUTH_MODE) === "app"
    ? githubDispatchAppConfigured(env)
    : githubDispatchTokenConfigured(env);
}

export async function getGitHubDispatchAccessToken(
  env: NodeJS.ProcessEnv = process.env,
): Promise<GitHubDispatchAccessToken> {
  const authMode = normalizeGitHubDispatchAuthMode(env.GITHUB_DISPATCH_AUTH_MODE);
  if (authMode === "token") {
    const token = String(env.KILL_LIFE_GITHUB_TOKEN || env.GITHUB_TOKEN || "").trim();
    if (!token) {
      throw new Error("Missing KILL_LIFE_GITHUB_TOKEN or GITHUB_TOKEN");
    }
    return { authMode, token, expiresAt: null };
  }

  const appId = String(env.GITHUB_APP_ID || "").trim();
  const privateKey = normalizeGitHubPrivateKey(String(env.GITHUB_APP_PRIVATE_KEY || ""));
  const installationId = String(env.GITHUB_APP_INSTALLATION_ID || "").trim();
  if (!appId || !privateKey || !installationId) {
    throw new Error(
      "Missing GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, or GITHUB_APP_INSTALLATION_ID",
    );
  }

  const auth = createAppAuth({
    appId,
    privateKey,
    installationId: Number(installationId),
  });
  const installation = await auth({
    type: "installation",
    installationId: Number(installationId),
  });

  return {
    authMode,
    token: installation.token,
    expiresAt: installation.expiresAt || null,
  };
}

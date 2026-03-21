import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "../AuthContext";

// Mock the api/client module
vi.mock("../../api/client", () => ({
  clearApiKey: vi.fn().mockResolvedValue(undefined),
  onAuth401: vi.fn().mockReturnValue(() => {}),
  setApiKey: vi.fn(),
  validateApiKey: vi.fn(),
}));

// Import the mocked functions so we can control them
import { setApiKey, validateApiKey, clearApiKey, onAuth401 } from "../../api/client";

const mockedSetApiKey = vi.mocked(setApiKey);
const mockedValidateApiKey = vi.mocked(validateApiKey);
const mockedClearApiKey = vi.mocked(clearApiKey);

// A helper component that exposes auth state for testing
function AuthConsumer() {
  const { authRequired, authenticated, checking, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="checking">{String(checking)}</span>
      <span data-testid="authenticated">{String(authenticated)}</span>
      <span data-testid="authRequired">{String(authRequired)}</span>
      <button onClick={() => login("test-key", false)}>Login</button>
      <button onClick={logout}>Logout</button>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: /health returns auth not required
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ auth_required: false }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  it("starts in checking state", () => {
    // Use a fetch that never resolves so we stay in checking state
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    expect(screen.getByTestId("checking").textContent).toBe("true");
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
  });

  it("sets authenticated=true when auth is not required", async () => {
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("checking").textContent).toBe("false");
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("authRequired").textContent).toBe("false");
  });

  it("validates existing key when auth is required", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ auth_required: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    mockedValidateApiKey.mockResolvedValue(true);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("checking").textContent).toBe("false");
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("authRequired").textContent).toBe("true");
  });

  it("sets authenticated=false when auth required and key invalid", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ auth_required: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    mockedValidateApiKey.mockResolvedValue(false);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("checking").textContent).toBe("false");
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(mockedClearApiKey).toHaveBeenCalled();
  });

  it("login sets authenticated on success", async () => {
    const user = userEvent.setup();
    mockedSetApiKey.mockResolvedValue(true);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("checking").textContent).toBe("false");
    });

    await user.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => {
      expect(screen.getByTestId("authenticated").textContent).toBe("true");
    });
    expect(mockedSetApiKey).toHaveBeenCalledWith("test-key", false);
  });

  it("logout clears authenticated state", async () => {
    const user = userEvent.setup();

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    // Wait for initial check to complete (auth not required -> authenticated=true)
    await waitFor(() => {
      expect(screen.getByTestId("checking").textContent).toBe("false");
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("true");

    await user.click(screen.getByRole("button", { name: "Logout" }));

    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(mockedClearApiKey).toHaveBeenCalled();
  });

  it("degrades gracefully when /health fetch fails", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network error"));

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("checking").textContent).toBe("false");
    });
    // Should not lock out the user
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("authRequired").textContent).toBe("false");
  });

  it("throws when useAuth is used outside AuthProvider", () => {
    // Suppress console.error from React for the expected error
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => render(<AuthConsumer />)).toThrow(
      "useAuth must be used within AuthProvider",
    );

    spy.mockRestore();
  });
});

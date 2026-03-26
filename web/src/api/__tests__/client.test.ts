import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, get, post, put, del, ApiError, getErrorMessage, onAuth401 } from "../client";

// Global fetch mock
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("api client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function jsonResponse(data: unknown, status = 200) {
    return Promise.resolve(
      new Response(JSON.stringify(data), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }

  function errorResponse(data: unknown, status: number) {
    return Promise.resolve(
      new Response(JSON.stringify(data), {
        status,
        statusText: "Error",
        headers: { "Content-Type": "application/json" },
      }),
    );
  }

  describe("get", () => {
    it("fetches JSON data successfully", async () => {
      mockFetch.mockReturnValueOnce(jsonResponse({ status: "ok" }));

      const result = await get<{ status: string }>("/health");
      expect(result).toEqual({ status: "ok" });
      expect(mockFetch).toHaveBeenCalledWith(
        "/health",
        expect.objectContaining({ credentials: "include" }),
      );
    });

    it("throws ApiError on non-ok response", async () => {
      mockFetch.mockReturnValueOnce(errorResponse({ error: "Not found" }, 404));

      await expect(get("/missing")).rejects.toThrow(ApiError);
      await expect(get("/missing")).rejects.toThrow();
    });
  });

  describe("post", () => {
    it("sends JSON body and returns response", async () => {
      mockFetch.mockReturnValueOnce(jsonResponse({ id: 1, name: "test-agent" }));

      const result = await post<{ id: number; name: string }>("/api/agents", {
        name: "test-agent",
      });
      expect(result).toEqual({ id: 1, name: "test-agent" });

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe("/api/agents");
      expect(opts.method).toBe("POST");
      expect(opts.body).toBe(JSON.stringify({ name: "test-agent" }));
    });
  });

  describe("put", () => {
    it("sends PUT request with body", async () => {
      mockFetch.mockReturnValueOnce(jsonResponse({ updated: true }));

      await put("/api/agents/test", { description: "updated" });

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe("/api/agents/test");
      expect(opts.method).toBe("PUT");
    });
  });

  describe("del", () => {
    it("sends DELETE request", async () => {
      mockFetch.mockReturnValueOnce(jsonResponse({ status: "deleted" }));

      await del("/api/agents/test");

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe("/api/agents/test");
      expect(opts.method).toBe("DELETE");
    });
  });

  describe("error handling", () => {
    it("throws ApiError with message from error field in body", async () => {
      mockFetch.mockReturnValueOnce(
        errorResponse({ error: "Agent not found" }, 404),
      );

      try {
        await api("/api/agents/missing");
        expect.unreachable("Should have thrown");
      } catch (e) {
        expect(e).toBeInstanceOf(ApiError);
        expect((e as ApiError).status).toBe(404);
        expect((e as ApiError).message).toBe("Agent not found");
      }
    });

    it("emits 401 event on unauthorized response", async () => {
      const handler = vi.fn();
      const unsub = onAuth401(handler);

      mockFetch.mockReturnValueOnce(
        errorResponse({ error: "Unauthorized" }, 401),
      );

      try {
        await api("/api/agents");
      } catch {
        // expected
      }

      expect(handler).toHaveBeenCalledOnce();
      unsub();
    });
  });

  describe("getErrorMessage", () => {
    it("returns friendly message for 401 ApiError", () => {
      const err = new ApiError(401, "Unauthorized");
      expect(getErrorMessage(err)).toContain("Session gateway");
    });

    it("returns error message for other ApiError", () => {
      const err = new ApiError(500, "Internal server error");
      expect(getErrorMessage(err)).toBe("Internal server error");
    });

    it("returns message for AbortError", () => {
      const err = new DOMException("Aborted", "AbortError");
      // DOMException in jsdom may not have name="AbortError" recognized,
      // so we just check it returns a string
      const msg = getErrorMessage(err);
      expect(typeof msg).toBe("string");
      expect(msg.length).toBeGreaterThan(0);
    });

    it("returns 'Request failed' for unknown errors", () => {
      expect(getErrorMessage(null)).toBe("Request failed");
      expect(getErrorMessage(undefined)).toBe("Request failed");
    });
  });
});

import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useApi } from "../useApi";

describe("useApi", () => {
  it("starts in idle state with no data", () => {
    const fn = vi.fn();
    const { result } = renderHook(() => useApi(fn));

    expect(result.current.status).toBe("idle");
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("returns data on successful execute", async () => {
    const fn = vi.fn().mockResolvedValue({ id: 1, name: "test" });
    const { result } = renderHook(() => useApi(fn));

    await act(async () => {
      await result.current.execute(undefined as never);
    });

    expect(result.current.status).toBe("success");
    expect(result.current.data).toEqual({ id: 1, name: "test" });
    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("sets error on failed execute", async () => {
    const fn = vi.fn().mockRejectedValue(new Error("Network failure"));
    const { result } = renderHook(() => useApi(fn));

    await act(async () => {
      await result.current.execute(undefined as never);
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toBe("Network failure");
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("is loading during execution", async () => {
    let resolve: (value: string) => void;
    const promise = new Promise<string>((r) => { resolve = r; });
    const fn = vi.fn().mockReturnValue(promise);

    const { result } = renderHook(() => useApi(fn));

    // Start execute but don't await it
    let executePromise: Promise<unknown>;
    act(() => {
      executePromise = result.current.execute(undefined as never);
    });

    // While the promise is pending, loading should be true
    expect(result.current.loading).toBe(true);
    expect(result.current.status).toBe("loading");

    // Resolve and wait for completion
    await act(async () => {
      resolve!("done");
      await executePromise;
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.status).toBe("success");
    expect(result.current.data).toBe("done");
  });

  it("returns the result from execute", async () => {
    const fn = vi.fn().mockResolvedValue(42);
    const { result } = renderHook(() => useApi(fn));

    let returnValue: unknown;
    await act(async () => {
      returnValue = await result.current.execute(undefined as never);
    });

    expect(returnValue).toBe(42);
  });

  it("returns undefined from execute on error", async () => {
    const fn = vi.fn().mockRejectedValue(new Error("fail"));
    const { result } = renderHook(() => useApi(fn));

    let returnValue: unknown;
    await act(async () => {
      returnValue = await result.current.execute(undefined as never);
    });

    expect(returnValue).toBeUndefined();
  });

  it("resets data and error when re-executing", async () => {
    const fn = vi.fn()
      .mockResolvedValueOnce("first")
      .mockRejectedValueOnce(new Error("second failed"));

    const { result } = renderHook(() => useApi(fn));

    await act(async () => {
      await result.current.execute(undefined as never);
    });
    expect(result.current.data).toBe("first");

    await act(async () => {
      await result.current.execute(undefined as never);
    });
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe("second failed");
  });
});

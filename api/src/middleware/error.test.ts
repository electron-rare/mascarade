import { describe, expect, it } from "vitest";
import { CoreApiError } from "../client/core.js";
import { handleCoreError } from "./error.js";

describe("handleCoreError", () => {
  it("preserves 4xx status codes from the core", () => {
    const result = handleCoreError(
      new CoreApiError("Agent not found", 404, { detail: "Agent not found" }),
    );

    expect(result).toEqual({
      status: 404,
      body: {
        detail: "Agent not found",
        core_status: 404,
      },
    });
  });

  it("maps core 5xx responses to 502", () => {
    const result = handleCoreError(
      new CoreApiError("Core exploded", 500, { detail: "Internal server error" }),
    );

    expect(result).toEqual({
      status: 502,
      body: {
        detail: "Internal server error",
        core_status: 500,
      },
    });
  });

  it("falls back to the error message when the core body is not structured", () => {
    const result = handleCoreError(new CoreApiError("Missing token", 401, "Missing token"));

    expect(result).toEqual({
      status: 401,
      body: {
        error: "Missing token",
        core_status: 401,
      },
    });
  });

  it("returns 502 when the core is unreachable", () => {
    expect(handleCoreError(new Error("boom"))).toEqual({
      status: 502,
      body: { error: "Core service unreachable" },
    });
  });
});

/**
 * Error handler centralise pour les routes proxy vers le core.
 */

import type { ContentfulStatusCode } from "hono/utils/http-status";
import { CoreApiError } from "../client/core.js";

export function handleCoreError(error: unknown) {
  if (error instanceof CoreApiError) {
    const status = (error.status >= 500 ? 502 : error.status) as ContentfulStatusCode;
    if (
      typeof error.coreBody === "object" &&
      error.coreBody !== null &&
      !Array.isArray(error.coreBody)
    ) {
      return {
        status,
        body: { ...(error.coreBody as Record<string, unknown>), core_status: error.status },
      };
    }
    return {
      status,
      body: { error: error.message, core_status: error.status },
    };
  }
  return {
    status: 502 as const,
    body: { error: "Core service unreachable" },
  };
}

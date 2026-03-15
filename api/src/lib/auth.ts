/**
 * Authentication library for database-backed user validation.
 * Provides functions to validate API tokens against the Python core service.
 */

import { coreClient } from "../client/core.js";

export interface RateLimits {
  requests_per_minute?: number | null;
  requests_per_hour?: number | null;
  requests_per_day?: number | null;
  tokens_per_day?: number | null;
}

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  role_id: number;
  is_active: boolean;
  rate_limits?: RateLimits | null;
}

/**
 * Validate a token against the database via the core service.
 * Returns user information if valid, null if invalid.
 */
export async function validateToken(token: string): Promise<AuthUser | null> {
  if (!token || token.length < 16) {
    return null;
  }

  try {
    const user = await coreClient.verifyToken(token);

    // Ensure user is active
    if (!user.is_active) {
      return null;
    }

    return user;
  } catch (error) {
    // Token is invalid or expired
    return null;
  }
}

/**
 * Check if database authentication is available.
 * Returns true if DATABASE_URL is configured.
 */
export function isDatabaseAuthAvailable(): boolean {
  // Check if DATABASE_URL is configured in the environment
  return Boolean(process.env.DATABASE_URL);
}

-- Rate limiting configuration for users and roles
-- Adds rate limit settings to enable per-user and per-role request throttling

-- Add rate_limits column to roles table (default limits for each role)
ALTER TABLE roles
ADD COLUMN IF NOT EXISTS rate_limits JSONB NOT NULL DEFAULT '{
    "requests_per_minute": null,
    "requests_per_hour": null,
    "requests_per_day": null,
    "tokens_per_day": null
}'::jsonb;

-- Add rate_limits column to users table (user-specific overrides)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS rate_limits JSONB DEFAULT NULL;

-- Add comment explaining the rate_limits structure
COMMENT ON COLUMN roles.rate_limits IS 'Default rate limits for this role: {requests_per_minute, requests_per_hour, requests_per_day, tokens_per_day}. Null values mean no limit.';
COMMENT ON COLUMN users.rate_limits IS 'User-specific rate limit overrides. If null, uses role defaults. Structure: {requests_per_minute, requests_per_hour, requests_per_day, tokens_per_day}';

-- Update default roles with appropriate rate limits
UPDATE roles SET rate_limits = '{
    "requests_per_minute": null,
    "requests_per_hour": null,
    "requests_per_day": null,
    "tokens_per_day": null
}'::jsonb WHERE name = 'admin';

UPDATE roles SET rate_limits = '{
    "requests_per_minute": 60,
    "requests_per_hour": 1000,
    "requests_per_day": 10000,
    "tokens_per_day": 1000000
}'::jsonb WHERE name = 'user';

UPDATE roles SET rate_limits = '{
    "requests_per_minute": 10,
    "requests_per_hour": 100,
    "requests_per_day": 500,
    "tokens_per_day": null
}'::jsonb WHERE name = 'read_only';

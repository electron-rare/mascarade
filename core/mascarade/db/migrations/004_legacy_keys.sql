-- Legacy API key migration support
-- Creates a table to track legacy keys that have been migrated to the database

-- Create legacy_migrations table to track what has been migrated
CREATE TABLE IF NOT EXISTS legacy_migrations (
    id SERIAL PRIMARY KEY,
    migration_type VARCHAR(50) NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    migrated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    notes TEXT
);

-- Create index for quick lookup
CREATE INDEX IF NOT EXISTS idx_legacy_migrations_key_prefix ON legacy_migrations(key_prefix);
CREATE INDEX IF NOT EXISTS idx_legacy_migrations_type ON legacy_migrations(migration_type);

-- Add comment explaining the table
COMMENT ON TABLE legacy_migrations IS 'Tracks legacy API keys that have been migrated to the database to prevent duplicate migrations';

-- Cost tracking schema for Mascarade LLM provider analytics
-- Stores per-request cost events for all LLM providers

CREATE DATABASE IF NOT EXISTS mascarade;

CREATE TABLE IF NOT EXISTS mascarade.cost_events
(
    timestamp DateTime64(3) DEFAULT now64(),
    provider String,
    model String,
    agent String,
    input_tokens UInt32,
    output_tokens UInt32,
    cost Float64,
    strategy String,
    success UInt8,
    request_id String DEFAULT '',
    user_id String DEFAULT '',
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 3,
    INDEX idx_provider provider TYPE set(100) GRANULARITY 3,
    INDEX idx_model model TYPE set(100) GRANULARITY 3
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (provider, model, timestamp)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Benchmark Results Table
-- Stores performance metrics for LLM provider benchmarks across different domains

CREATE TABLE IF NOT EXISTS benchmarks (
    -- Identification
    provider String,
    model String,
    domain String,

    -- Performance Metrics
    latency_p50 Float64,
    latency_p95 Float64,
    quality_score Float64,
    cost Float64,

    -- Metadata
    timestamp DateTime DEFAULT now(),
    benchmark_id String DEFAULT generateUUIDv4(),

    -- Additional context (optional but useful)
    request_count UInt32 DEFAULT 0,
    error_rate Float64 DEFAULT 0.0,
    notes String DEFAULT ''
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (provider, model, domain, timestamp)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Index for efficient querying by domain and timestamp
CREATE INDEX IF NOT EXISTS idx_domain_timestamp ON benchmarks (domain, timestamp) TYPE minmax GRANULARITY 4;

-- Index for efficient cost analysis
CREATE INDEX IF NOT EXISTS idx_cost ON benchmarks (cost) TYPE minmax GRANULARITY 4;

-- Index for quality score filtering
CREATE INDEX IF NOT EXISTS idx_quality ON benchmarks (quality_score) TYPE minmax GRANULARITY 4;

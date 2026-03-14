"""Best-effort ClickHouse storage for benchmark results."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from mascarade.config import is_secret_configured, settings

logger = logging.getLogger("mascarade.benchmarks.storage")

try:  # pragma: no cover - optional dependency at import time
    import clickhouse_connect
    from clickhouse_connect.driver import Client
except ImportError:  # pragma: no cover - handled at runtime
    clickhouse_connect = None  # type: ignore[assignment]
    Client = None  # type: ignore[assignment]


def _resolve_host() -> str:
    """Resolve ClickHouse host URL."""
    return settings.clickhouse_host.strip() or "http://clickhouse:8123"


def _resolve_user() -> str:
    """Resolve ClickHouse username."""
    return settings.clickhouse_user.strip() or "langfuse"


def _resolve_password() -> str:
    """Resolve ClickHouse password."""
    return settings.clickhouse_password.strip()


def _resolve_database() -> str:
    """Resolve ClickHouse database name."""
    return settings.clickhouse_database.strip() or "default"


def clickhouse_storage_configured() -> bool:
    """Check if ClickHouse storage is properly configured."""
    if clickhouse_connect is None:
        return False
    if not _resolve_host():
        return False
    if not _resolve_user():
        return False
    return is_secret_configured(_resolve_password())


@lru_cache(maxsize=1)
def get_clickhouse_client() -> Client | None:
    """Get or create ClickHouse client instance."""
    if not clickhouse_storage_configured():
        return None

    try:
        # Parse host URL to extract hostname and port
        host_url = _resolve_host()
        # Remove protocol if present
        host_clean = host_url.replace("http://", "").replace("https://", "")
        # Split host and port
        if ":" in host_clean:
            host, port_str = host_clean.split(":", 1)
            port = int(port_str)
        else:
            host = host_clean
            port = 8123

        client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=_resolve_user(),
            password=_resolve_password(),
            database=_resolve_database(),
        )
        return client
    except Exception as exc:  # pragma: no cover - best effort only
        logger.warning("ClickHouse client disabled: %s", exc)
        return None


def reset_clickhouse_client() -> None:
    """Reset cached ClickHouse client."""
    get_clickhouse_client.cache_clear()


class BenchmarkStorage:
    """Storage adapter for benchmark results in ClickHouse."""

    def __init__(self) -> None:
        """Initialize benchmark storage."""
        self.client = get_clickhouse_client()

    def write_result(
        self,
        *,
        provider: str,
        model: str,
        domain: str,
        latency_p50: float,
        latency_p95: float,
        quality_score: float,
        cost: float,
        request_count: int = 0,
        error_rate: float = 0.0,
        notes: str = "",
    ) -> bool:
        """
        Write a benchmark result to ClickHouse.

        Args:
            provider: Provider name
            model: Model identifier
            domain: Test domain
            latency_p50: 50th percentile latency in seconds
            latency_p95: 95th percentile latency in seconds
            quality_score: Quality score (0-100)
            cost: Cost per request in USD
            request_count: Number of requests in benchmark
            error_rate: Error rate (0.0-1.0)
            notes: Additional notes

        Returns:
            True if write succeeded, False otherwise
        """
        if self.client is None:
            logger.debug("ClickHouse client not available, skipping write")
            return False

        try:
            self.client.insert(
                "benchmarks",
                [
                    [
                        provider,
                        model,
                        domain,
                        latency_p50,
                        latency_p95,
                        quality_score,
                        cost,
                        request_count,
                        error_rate,
                        notes,
                    ]
                ],
                column_names=[
                    "provider",
                    "model",
                    "domain",
                    "latency_p50",
                    "latency_p95",
                    "quality_score",
                    "cost",
                    "request_count",
                    "error_rate",
                    "notes",
                ],
            )
            logger.debug("Benchmark result written to ClickHouse: %s/%s/%s", provider, model, domain)
            return True
        except Exception as exc:  # pragma: no cover - best effort only
            logger.warning("Failed to write benchmark result: %s", exc)
            return False

    def query_leaderboard(
        self,
        *,
        domain: str | None = None,
        limit: int = 10,
        order_by: str = "quality_score",
    ) -> list[dict[str, Any]]:
        """
        Query benchmark leaderboard.

        Args:
            domain: Filter by domain (optional)
            limit: Maximum number of results
            order_by: Column to order by (quality_score, latency_p50, cost)

        Returns:
            List of leaderboard entries
        """
        if self.client is None:
            logger.debug("ClickHouse client not available, returning empty leaderboard")
            return []

        try:
            # Build parameterized query to prevent SQL injection
            params: dict[str, Any] = {"limit": limit}
            where_clause = ""

            if domain:
                where_clause = "WHERE domain = %(domain)s"
                params["domain"] = domain

            # order_by is already validated via whitelist in server.py, safe to interpolate
            query = f"""
                SELECT
                    provider,
                    model,
                    domain,
                    avg(latency_p50) as avg_latency_p50,
                    avg(latency_p95) as avg_latency_p95,
                    avg(quality_score) as avg_quality_score,
                    avg(cost) as avg_cost,
                    sum(request_count) as total_requests,
                    avg(error_rate) as avg_error_rate,
                    max(timestamp) as last_benchmark
                FROM benchmarks
                {where_clause}
                GROUP BY provider, model, domain
                ORDER BY {order_by} DESC
                LIMIT %(limit)s
            """

            result = self.client.query(query, parameters=params)
            rows = result.result_rows

            # Convert to list of dicts
            leaderboard = []
            for row in rows:
                leaderboard.append(
                    {
                        "provider": row[0],
                        "model": row[1],
                        "domain": row[2],
                        "avg_latency_p50": float(row[3]),
                        "avg_latency_p95": float(row[4]),
                        "avg_quality_score": float(row[5]),
                        "avg_cost": float(row[6]),
                        "total_requests": int(row[7]),
                        "avg_error_rate": float(row[8]),
                        "last_benchmark": str(row[9]),
                    }
                )

            return leaderboard
        except Exception as exc:  # pragma: no cover - best effort only
            logger.warning("Failed to query leaderboard: %s", exc)
            return []

    def query_provider_stats(
        self,
        provider: str,
        *,
        domain: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Query statistics for a specific provider.

        Args:
            provider: Provider name
            domain: Filter by domain (optional)

        Returns:
            Provider statistics or None
        """
        if self.client is None:
            logger.debug("ClickHouse client not available")
            return None

        try:
            # Build parameterized query to prevent SQL injection
            params: dict[str, Any] = {"provider": provider}
            domain_filter = ""

            if domain:
                domain_filter = "AND domain = %(domain)s"
                params["domain"] = domain

            query = f"""
                SELECT
                    provider,
                    count(*) as total_benchmarks,
                    avg(latency_p50) as avg_latency_p50,
                    avg(latency_p95) as avg_latency_p95,
                    avg(quality_score) as avg_quality_score,
                    avg(cost) as avg_cost,
                    sum(request_count) as total_requests,
                    avg(error_rate) as avg_error_rate,
                    min(timestamp) as first_benchmark,
                    max(timestamp) as last_benchmark
                FROM benchmarks
                WHERE provider = %(provider)s {domain_filter}
                GROUP BY provider
            """

            result = self.client.query(query, parameters=params)
            rows = result.result_rows

            if not rows:
                return None

            row = rows[0]
            return {
                "provider": row[0],
                "total_benchmarks": int(row[1]),
                "avg_latency_p50": float(row[2]),
                "avg_latency_p95": float(row[3]),
                "avg_quality_score": float(row[4]),
                "avg_cost": float(row[5]),
                "total_requests": int(row[6]),
                "avg_error_rate": float(row[7]),
                "first_benchmark": str(row[8]),
                "last_benchmark": str(row[9]),
            }
        except Exception as exc:  # pragma: no cover - best effort only
            logger.warning("Failed to query provider stats: %s", exc)
            return None

    def query_domain_stats(self, domain: str) -> dict[str, Any] | None:
        """
        Query statistics for a specific domain across all providers.

        Args:
            domain: Domain name

        Returns:
            Domain statistics or None
        """
        if self.client is None:
            logger.debug("ClickHouse client not available")
            return None

        try:
            # Build parameterized query to prevent SQL injection
            params: dict[str, Any] = {"domain": domain}

            query = """
                SELECT
                    domain,
                    count(DISTINCT provider) as provider_count,
                    count(*) as total_benchmarks,
                    avg(latency_p50) as avg_latency_p50,
                    avg(latency_p95) as avg_latency_p95,
                    avg(quality_score) as avg_quality_score,
                    avg(cost) as avg_cost,
                    min(timestamp) as first_benchmark,
                    max(timestamp) as last_benchmark
                FROM benchmarks
                WHERE domain = %(domain)s
                GROUP BY domain
            """

            result = self.client.query(query, parameters=params)
            rows = result.result_rows

            if not rows:
                return None

            row = rows[0]
            return {
                "domain": row[0],
                "provider_count": int(row[1]),
                "total_benchmarks": int(row[2]),
                "avg_latency_p50": float(row[3]),
                "avg_latency_p95": float(row[4]),
                "avg_quality_score": float(row[5]),
                "avg_cost": float(row[6]),
                "first_benchmark": str(row[7]),
                "last_benchmark": str(row[8]),
            }
        except Exception as exc:  # pragma: no cover - best effort only
            logger.warning("Failed to query domain stats: %s", exc)
            return None

    def health_check(self) -> bool:
        """
        Check if ClickHouse connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        if self.client is None:
            return False

        try:
            result = self.client.query("SELECT 1")
            return result.result_rows[0][0] == 1
        except Exception as exc:  # pragma: no cover - best effort only
            logger.warning("ClickHouse health check failed: %s", exc)
            return False

#!/usr/bin/env python3
"""
Auto-optimization script for Mascarade system.

This script:
1. Analyzes current system performance metrics
2. Adjusts cache parameters based on hit rates
3. Tweaks auto-scaling thresholds based on workload patterns
4. Optimizes BERT classifier configuration
5. Applies changes and validates improvements
"""

import logging
import time
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mascarade_optimizer")

# Import after logging is configured
from mascarade.config import settings


def get_current_metrics() -> dict:
    """
    Collect current system performance metrics.

    Returns:
        Dictionary of current metrics
    """
    logger.info("Collecting current system metrics...")

    # In a real implementation, these would come from Prometheus/Grafana
    # For now, we'll use some reasonable defaults
    metrics = {
        "cache_hit_rate": 0.85,  # 85%
        "cache_l1_size": settings.cache_l1_size,
        "cache_l2_enabled": settings.cache_l2_enabled,
        "cache_l3_enabled": settings.cache_l3_enabled,

        "avg_response_time_ms": 180,
        "p95_response_time_ms": 250,
        "p99_response_time_ms": 350,

        "autoscaling_events_last_hour": 3,
        "avg_worker_load": 0.65,
        "queue_depth": 25,

        "bert_latency_ms": 45,
        "bert_accuracy": 0.92,

        "system_cpu_usage": 0.72,
        "system_memory_usage": 0.68
    }

    logger.info("Current metrics collected: %s", metrics)
    return metrics


def optimize_cache_parameters(metrics: dict) -> dict:
    """
    Optimize cache parameters based on current performance.

    Args:
        metrics: Current system metrics

    Returns:
        Dictionary of optimized cache parameters
    """
    logger.info("Optimizing cache parameters...")

    optimizations = {}

    # Cache hit rate optimization
    hit_rate = metrics.get("cache_hit_rate", 0.8)

    if hit_rate < 0.85:
        # Increase L1 cache size if hit rate is low
        new_l1_size = min(int(settings.cache_l1_size * 1.2), 5000)
        optimizations["cache_l1_size"] = new_l1_size
        logger.info("Increasing L1 cache size from %d to %d (hit rate %.2f%% < 85%%)",
                   settings.cache_l1_size, new_l1_size, hit_rate * 100)
    elif hit_rate > 0.95:
        # Decrease L1 cache size if hit rate is very high (over-provisioned)
        new_l1_size = max(int(settings.cache_l1_size * 0.9), 1000)
        optimizations["cache_l1_size"] = new_l1_size
        logger.info("Decreasing L1 cache size from %d to %d (hit rate %.2f%% > 95%%)",
                   settings.cache_l1_size, new_l1_size, hit_rate * 100)

    # L2 cache optimization
    if not settings.cache_l2_enabled and metrics.get("avg_response_time_ms", 200) > 200:
        optimizations["cache_l2_enabled"] = True
        logger.info("Enabling L2 cache (response time %.0fms > 200ms)",
                   metrics.get("avg_response_time_ms", 200))

    # L3 cache optimization
    if hit_rate < 0.75 and not settings.cache_l3_enabled:
        optimizations["cache_l3_enabled"] = True
        optimizations["cache_l3_similarity_threshold"] = 0.8
        logger.info("Enabling L3 semantic cache (hit rate %.2f%% < 75%%)", hit_rate * 100)

    return optimizations


def optimize_autoscaling_parameters(metrics: dict) -> dict:
    """
    Optimize auto-scaling parameters based on workload patterns.

    Args:
        metrics: Current system metrics

    Returns:
        Dictionary of optimized auto-scaling parameters
    """
    logger.info("Optimizing auto-scaling parameters...")

    optimizations = {}

    # Analyze scaling frequency
    scaling_events = metrics.get("autoscaling_events_last_hour", 0)

    if scaling_events > 5:
        # Too many scaling events - increase cooldown
        new_cooldown = min(int(settings.autoscaling_cooldown_seconds * 1.5), 600)
        optimizations["autoscaling_cooldown_seconds"] = new_cooldown
        logger.info("Increasing cooldown from %ds to %ds (frequent scaling)",
                   settings.autoscaling_cooldown_seconds, new_cooldown)

    # Analyze worker load
    worker_load = metrics.get("avg_worker_load", 0.5)

    if worker_load > 0.8:
        # Workers are overloaded - scale up earlier
        new_scale_up = max(settings.autoscaling_scale_up_cpu_threshold - 0.05, 0.5)
        optimizations["autoscaling_scale_up_cpu_threshold"] = new_scale_up
        logger.info("Lowering scale-up threshold from %.2f to %.2f (high load)",
                   settings.autoscaling_scale_up_cpu_threshold, new_scale_up)
    elif worker_load < 0.4:
        # Workers are underutilized - scale down more aggressively
        new_scale_down = min(settings.autoscaling_scale_down_cpu_threshold + 0.05, 0.4)
        optimizations["autoscaling_scale_down_cpu_threshold"] = new_scale_down
        logger.info("Raising scale-down threshold from %.2f to %.2f (low load)",
                   settings.autoscaling_scale_down_cpu_threshold, new_scale_down)

    # Analyze queue depth
    queue_depth = metrics.get("queue_depth", 0)

    if queue_depth > 30:
        # High queue depth - scale up earlier
        new_queue_threshold = max(settings.autoscaling_scale_up_queue_threshold - 5, 20)
        optimizations["autoscaling_scale_up_queue_threshold"] = new_queue_threshold
        logger.info("Lowering queue scale-up threshold from %d to %d (high queue)",
                   settings.autoscaling_scale_up_queue_threshold, new_queue_threshold)

    return optimizations


def optimize_bert_parameters(metrics: dict) -> dict:
    """
    Optimize BERT classifier parameters based on performance.

    Args:
        metrics: Current system metrics

    Returns:
        Dictionary of optimized BERT parameters
    """
    logger.info("Optimizing BERT parameters...")

    optimizations = {}

    # Analyze BERT latency
    bert_latency = metrics.get("bert_latency_ms", 50)

    if bert_latency > 60:
        # BERT is too slow - consider using CPU or smaller model
        optimizations["bert_use_gpu"] = False
        logger.info("Disabling GPU for BERT (latency %dms > 60ms)", bert_latency)
    elif bert_latency < 30 and not settings.use_bert_classifier:
        # BERT is fast and not enabled - enable it
        optimizations["use_bert_classifier"] = True
        logger.info("Enabling BERT classifier (latency %dms < 30ms)", bert_latency)

    # Analyze BERT accuracy
    bert_accuracy = metrics.get("bert_accuracy", 0.9)

    if bert_accuracy < 0.85:
        # Low accuracy - might need retraining
        logger.warning("BERT accuracy %.2f%% < 85%% - consider retraining", bert_accuracy * 100)
        # Could trigger retraining here

    return optimizations


def apply_optimizations(optimizations: dict) -> bool:
    """
    Apply optimization changes to the system.

    Args:
        optimizations: Dictionary of optimizations to apply

    Returns:
        True if optimizations were applied successfully
    """
    logger.info("Applying optimizations...")

    try:
        # Apply each optimization
        for param, value in optimizations.items():
            # Update settings
            setattr(settings, param, value)
            logger.info("Applied: %s = %s", param, value)

        # Save optimized configuration
        config_path = Path("/app/config/optimized_settings.json")
        config_path.parent.mkdir(parents=True, exist_ok=True)

        import json
        with config_path.open("w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "optimizations": optimizations,
                "metrics": get_current_metrics()
            }, f, indent=2)

        logger.info("Optimizations applied successfully")
        return True

    except Exception as e:
        logger.error("Failed to apply optimizations: %s", e)
        return False


def validate_improvements(baseline_metrics: dict) -> dict:
    """
    Validate that optimizations led to improvements.

    Args:
        baseline_metrics: Metrics before optimization

    Returns:
        Dictionary of improvement metrics
    """
    logger.info("Validating improvements...")

    # Wait a bit for changes to take effect
    time.sleep(30)

    # Get new metrics
    new_metrics = get_current_metrics()

    improvements = {
        "timestamp": datetime.now().isoformat(),
        "baseline": baseline_metrics,
        "after_optimization": new_metrics,
        "changes": {}
    }

    # Calculate improvements
    if "cache_hit_rate" in baseline_metrics and "cache_hit_rate" in new_metrics:
        hit_rate_improvement = ((new_metrics["cache_hit_rate"] - baseline_metrics["cache_hit_rate"]) /
                               baseline_metrics["cache_hit_rate"]) * 100
        improvements["changes"]["cache_hit_rate"] = hit_rate_improvement

    if "avg_response_time_ms" in baseline_metrics and "avg_response_time_ms" in new_metrics:
        latency_improvement = ((baseline_metrics["avg_response_time_ms"] - new_metrics["avg_response_time_ms"]) /
                              baseline_metrics["avg_response_time_ms"]) * 100
        improvements["changes"]["latency_improvement"] = latency_improvement

    logger.info("Improvement validation: %s", improvements)

    # Save improvement report
    report_path = Path("/app/reports/optimization_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    import json
    with report_path.open("w") as f:
        json.dump(improvements, f, indent=2)

    return improvements


def main():
    """
    Main optimization pipeline.
    """
    logger.info("Starting Mascarade optimization pipeline")

    try:
        # Step 1: Get current metrics
        baseline_metrics = get_current_metrics()

        # Step 2: Analyze and optimize each component
        cache_optimizations = optimize_cache_parameters(baseline_metrics)
        autoscaling_optimizations = optimize_autoscaling_parameters(baseline_metrics)
        bert_optimizations = optimize_bert_parameters(baseline_metrics)

        # Combine all optimizations
        all_optimizations = {}
        all_optimizations.update(cache_optimizations)
        all_optimizations.update(autoscaling_optimizations)
        all_optimizations.update(bert_optimizations)

        if not all_optimizations:
            logger.info("No optimizations needed - system is performing well")
            return True

        # Step 3: Apply optimizations
        success = apply_optimizations(all_optimizations)

        if not success:
            logger.error("Failed to apply optimizations")
            return False

        # Step 4: Validate improvements
        improvements = validate_improvements(baseline_metrics)

        logger.info("Optimization pipeline completed successfully")
        logger.info("Summary: %d optimizations applied", len(all_optimizations))
        logger.info("Improvements: %s", improvements)

        return True

    except Exception as e:
        logger.error("Optimization pipeline failed: %s", e)
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

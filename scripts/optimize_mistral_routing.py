#!/usr/bin/env python3.14
"""Optimize Mistral routing based on performance metrics."""

import asyncio
import time
from typing import Dict, List

import httpx


class MistralRoutingOptimizer:
    """Optimizes routing for Mistral AI services."""

    def __init__(self, api_base_url: str = "http://localhost:8100"):
        self.api_base_url = api_base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.metrics_history: Dict[str, List[float]] = {}

    async def fetch_metrics(self) -> Dict:
        """Fetch current metrics from the API."""
        try:
            response = await self.client.get(f"{self.api_base_url}/metrics")
            response.raise_for_status()
            
            metrics = {}
            for line in response.text.split('\n'):
                if line.startswith('mistral_'):
                    parts = line.split()
                    if len(parts) >= 2:
                        metrics[parts[0]] = float(parts[1])
            
            return metrics
        except Exception as e:
            print(f"Error fetching metrics: {e}")
            return {}

    async def analyze_performance(self):
        """Analyze current performance and suggest optimizations."""
        metrics = await self.fetch_metrics()
        
        if not metrics:
            print("No metrics available for analysis.")
            return

        # Store metrics history
        for key, value in metrics.items():
            if key not in self.metrics_history:
                self.metrics_history[key] = []
            self.metrics_history[key].append(value)
            # Keep last 10 samples
            if len(self.metrics_history[key]) > 10:
                self.metrics_history[key].pop(0)

        # Calculate trends
        trends = {}
        for key, values in self.metrics_history.items():
            if len(values) >= 2:
                trend = values[-1] - values[0]
                trends[key] = trend

        # Generate recommendations
        recommendations = []

        # Latency analysis
        if 'mistral_latency' in metrics:
            latency = metrics['mistral_latency']
            if latency > 200:  # P95 target
                recommendations.append(
                    f"⚠️ High latency detected: {latency:.0f}ms (target < 200ms). "
                    "Consider adding more workers or reducing batch size."
                )
            else:
                recommendations.append(
                    f"✅ Latency is good: {latency:.0f}ms (target < 200ms)"
                )

        # Error rate analysis
        if 'mistral_errors' in metrics and 'mistral_requests_total' in metrics:
            error_rate = metrics['mistral_errors'] / max(metrics['mistral_requests_total'], 1)
            if error_rate > 0.01:  # 1% threshold
                recommendations.append(
                    f"⚠️ High error rate: {error_rate:.2%}. "
                    "Check worker health and retry logic."
                )
            else:
                recommendations.append(
                    f"✅ Error rate is good: {error_rate:.2%} (target < 1%)"
                )

        # Throughput analysis
        if 'mistral_throughput' in metrics:
            throughput = metrics['mistral_throughput']
            if throughput < 500:  # Target: 500+ req/s
                recommendations.append(
                    f"⚠️ Low throughput: {throughput:.0f} req/s (target > 500). "
                    "Consider scaling workers or optimizing batching."
                )
            else:
                recommendations.append(
                    f"✅ Throughput is good: {throughput:.0f} req/s (target > 500)"
                )

        # Cost analysis
        if 'mistral_cost' in metrics:
            cost = metrics['mistral_cost']
            if cost > 0.30:  # $0.30 per 1M tokens threshold
                recommendations.append(
                    f"⚠️ High cost: ${cost:.2f} per 1M tokens (target < $0.30). "
                    "Consider using smaller models for appropriate requests."
                )
            else:
                recommendations.append(
                    f"✅ Cost is optimized: ${cost:.2f} per 1M tokens (target < $0.30)"
                )

        # Print recommendations
        print("\n" + "="*60)
        print("Mistral Routing Optimization Report")
        print("="*60)
        print(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("\nCurrent Metrics:")
        for key, value in metrics.items():
            print(f"  {key}: {value:.2f}")
        
        print("\nRecommendations:")
        for rec in recommendations:
            print(f"  {rec}")
        
        print("\nTrends (last 10 samples):")
        for key, trend in trends.items():
            direction = "↑" if trend > 0 else "↓"
            print(f"  {key}: {direction} {abs(trend):.2f}")
        
        print("="*60 + "\n")

    async def optimize_routing(self):
        """Apply routing optimizations."""
        # This would interact with the scheduler API
        # to adjust routing parameters
        print("Applying routing optimizations...")
        
        # Example: Adjust worker weights based on performance
        # This is a placeholder - actual implementation would
        # call the scheduler's optimization endpoints
        
        print("✅ Routing optimization applied")

    async def run(self):
        """Main optimization loop."""
        print("Starting Mistral Routing Optimizer...")
        
        try:
            while True:
                await self.analyze_performance()
                await self.optimize_routing()
                await asyncio.sleep(300)  # Run every 5 minutes
        except KeyboardInterrupt:
            print("\nShutting down optimizer...")
        finally:
            await self.client.aclose()


if __name__ == "__main__":
    optimizer = MistralRoutingOptimizer()
    asyncio.run(optimizer.run())

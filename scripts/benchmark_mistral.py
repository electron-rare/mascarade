#!/usr/bin/env python3.14
"""Benchmark Mistral AI services performance."""

import asyncio
import time
from typing import Dict, List

import httpx


class MistralBenchmark:
    """Benchmark Mistral AI services."""

    def __init__(self, api_base_url: str = "http://localhost:8100"):
        self.api_base_url = api_base_url
        self.client = httpx.AsyncClient(timeout=60.0)

    async def benchmark_latency(
        self,
        model: str,
        num_requests: int = 100,
        concurrent: int = 10
    ) -> Dict:
        """Benchmark request latency."""
        semaphore = asyncio.Semaphore(concurrent)
        
        async def make_request():
            async with semaphore:
                start = time.time()
                try:
                    response = await self.client.post(
                        f"{self.api_base_url}/api/agents/send",
                        json={
                            "messages": [{"role": "user", "content": "Benchmark test"}],
                            "model": model,
                            "strategy": "specific",
                            "provider": "mistral-studio"
                        },
                        timeout=30
                    )
                    latency = (time.time() - start) * 1000
                    return latency, True
                except Exception:
                    return (time.time() - start) * 1000, False
        
        tasks = [make_request() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        
        latencies = [r[0] for r in results if r[1]]
        success_rate = sum(1 for r in results if r[1]) / len(results)
        
        return {
            "p50": sorted(latencies)[len(latencies)//2],
            "p90": sorted(latencies)[int(len(latencies)*0.9)],
            "p95": sorted(latencies)[int(len(latencies)*0.95)],
            "p99": sorted(latencies)[int(len(latencies)*0.99)],
            "success_rate": success_rate,
            "total_requests": num_requests,
            "failed_requests": num_requests - len(latencies)
        }

    async def benchmark_throughput(
        self,
        model: str,
        duration: int = 60
    ) -> Dict:
        """Benchmark request throughput."""
        end_time = time.time() + duration
        request_count = 0
        success_count = 0
        
        while time.time() < end_time:
            try:
                response = await self.client.post(
                    f"{self.api_base_url}/api/agents/send",
                    json={
                        "messages": [{"role": "user", "content": "Throughput test"}],
                        "model": model,
                        "strategy": "specific",
                        "provider": "mistral-studio"
                    },
                    timeout=10
                )
                success_count += 1
            except Exception:
                pass
            
            request_count += 1
        
        return {
            "throughput": request_count / duration,
            "success_throughput": success_count / duration,
            "error_rate": 1 - (success_count / request_count),
            "duration": duration
        }

    async def benchmark_embeddings(
        self,
        num_requests: int = 100
    ) -> Dict:
        """Benchmark embeddings performance."""
        start = time.time()
        
        tasks = []
        for _ in range(num_requests):
            tasks.append(
                self.client.post(
                    f"{self.api_base_url}/api/embeddings",
                    json={
                        "texts": ["Benchmark text"],
                        "provider": "mistral-embeddings"
                    },
                    timeout=10
                )
            )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        
        return {
            "latency": (time.time() - start) / num_requests * 1000,
            "throughput": num_requests / (time.time() - start),
            "success_rate": success_count / num_requests,
            "total_requests": num_requests
        }

    async def run_benchmarks(self):
        """Run all benchmarks."""
        print("\n" + "="*60)
        print("Mistral AI Benchmark Suite")
        print("="*60)
        
        # Latency benchmark
        print("\n📊 Running Latency Benchmark...")
        latency_results = await self.benchmark_latency("mistral-large-latest")
        print(f"  P50: {latency_results['p50']:.0f}ms")
        print(f"  P95: {latency_results['p95']:.0f}ms")
        print(f"  P99: {latency_results['p99']:.0f}ms")
        print(f"  Success Rate: {latency_results['success_rate']:.1%}")
        
        # Throughput benchmark
        print("\n📊 Running Throughput Benchmark...")
        throughput_results = await self.benchmark_throughput("mistral-large-latest")
        print(f"  Throughput: {throughput_results['throughput']:.1f} req/s")
        print(f"  Success Throughput: {throughput_results['success_throughput']:.1f} req/s")
        print(f"  Error Rate: {throughput_results['error_rate']:.1%}")
        
        # Embeddings benchmark
        print("\n📊 Running Embeddings Benchmark...")
        embeddings_results = await self.benchmark_embeddings()
        print(f"  Latency: {embeddings_results['latency']:.0f}ms")
        print(f"  Throughput: {embeddings_results['throughput']:.1f} req/s")
        print(f"  Success Rate: {embeddings_results['success_rate']:.1%}")
        
        # Generate report
        print("\n" + "="*60)
        print("Benchmark Report Summary")
        print("="*60)
        
        # Latency score (lower is better)
        latency_score = min(100, max(0, 100 - (latency_results['p95'] / 200 * 100)))
        
        # Throughput score (higher is better)
        throughput_score = min(100, max(0, throughput_results['throughput'] / 500 * 100))
        
        # Reliability score
        reliability_score = min(100, max(0, latency_results['success_rate'] * 100))
        
        # Overall score
        overall_score = (latency_score * 0.4 + throughput_score * 0.4 + reliability_score * 0.2)
        
        print(f"\nScores:")
        print(f"  Latency: {latency_score:.0f}/100")
        print(f"  Throughput: {throughput_score:.0f}/100")
        print(f"  Reliability: {reliability_score:.0f}/100")
        print(f"  Overall: {overall_score:.0f}/100")
        
        if overall_score >= 90:
            grade = "A+ (Excellent)"
        elif overall_score >= 80:
            grade = "A (Very Good)"
        elif overall_score >= 70:
            grade = "B (Good)"
        elif overall_score >= 60:
            grade = "C (Fair)"
        else:
            grade = "D (Needs Improvement)"
        
        print(f"\nGrade: {grade}")
        print("="*60 + "\n")

    async def close(self):
        """Clean up resources."""
        await self.client.aclose()


async def main():
    benchmark = MistralBenchmark()
    try:
        await benchmark.run_benchmarks()
    finally:
        await benchmark.close()


if __name__ == "__main__":
    asyncio.run(main())

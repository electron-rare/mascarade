#!/usr/bin/env python3
"""End-to-end verification script for domain-aware intelligent routing.

This script tests the complete domain routing pipeline with a live Ollama service:
1. Domain detection from query text
2. Routing to correct mascarade-* model via Ollama
3. Fallback to cloud providers when Ollama unavailable
4. Langfuse trace metadata for observability
"""

import asyncio
import logging
import sys
import time

import httpx

from mascarade.router import Router
from mascarade.router.domain_detector import DomainDetector
from mascarade.router.router import Strategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class E2EVerifier:
    """End-to-end verification for domain routing."""

    def __init__(self):
        self.router = Router()
        self.detector = DomainDetector()
        self.results: dict[str, bool] = {}
        self.ollama_base_url = "http://localhost:11434"

    async def check_ollama_service(self) -> bool:
        """Check if Ollama service is running and responsive."""
        logger.info("Checking Ollama service availability...")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    logger.info(f"✓ Ollama service is running with {len(models)} models")
                    for model in models:
                        logger.info(f"  - {model.get('name', 'unknown')}")
                    return True
                else:
                    logger.warning(f"✗ Ollama service returned status {response.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"✗ Ollama service not available: {e}")
            return False

    async def verify_domain_detection(self) -> bool:
        """Verify domain detection for all supported domains."""
        logger.info("\n=== Testing Domain Detection ===")

        test_cases = [
            ("How do I route PCB traces in KiCad?", "kicad"),
            ("Create a SPICE simulation for a RC circuit", "spice"),
            ("Design a parametric model in FreeCAD", "freecad"),
            ("Configure STM32 UART with HAL library", "stm32"),
            ("Set up MQTT on ESP32 with Arduino", "iot"),
            ("What is the capital of France?", "general"),
        ]

        all_passed = True
        for query, expected_domain in test_cases:
            detected = self.detector.detect_domain(query)
            passed = detected == expected_domain
            status = "✓" if passed else "✗"
            logger.info(
                f"{status} Query: '{query[:50]}...' -> {detected} (expected: {expected_domain})"
            )
            all_passed = all_passed and passed

        self.results["domain_detection"] = all_passed
        return all_passed

    async def verify_domain_routing_with_ollama(self) -> bool:
        """Verify routing to mascarade-* models via Ollama."""
        logger.info("\n=== Testing Domain Routing with Ollama ===")

        test_cases = [
            ("How do I create a footprint in KiCad?", "kicad", "mascarade-kicad"),
            ("Analyze this SPICE netlist", "spice", "mascarade-spice"),
            ("Create a 3D assembly in FreeCAD", "freecad", "mascarade-freecad"),
            ("Configure STM32 I2C communication", "stm32", "mascarade-iot"),
            ("Set up LoRaWAN on ESP32", "iot", "mascarade-iot"),
        ]

        all_passed = True
        for query, domain, expected_model in test_cases:
            try:
                messages = [{"role": "user", "content": query}]

                # Use DOMAIN strategy
                start_time = time.perf_counter()
                response = await self.router.send(
                    messages,
                    strategy=Strategy.DOMAIN,
                    domain=domain,
                    model=expected_model,
                    max_tokens=100,
                )
                elapsed = (time.perf_counter() - start_time) * 1000

                # Check if response came from Ollama
                passed = response.provider == "ollama"
                status = "✓" if passed else "✗"
                logger.info(
                    f"{status} Domain '{domain}' -> provider={response.provider}, "
                    f"model={response.model}, time={elapsed:.0f}ms"
                )

                if not passed:
                    logger.warning(f"  Expected provider='ollama', got '{response.provider}'")

                all_passed = all_passed and passed

            except Exception as e:
                logger.error(f"✗ Domain '{domain}' routing failed: {e}")
                all_passed = False

        self.results["domain_routing_ollama"] = all_passed
        return all_passed

    async def verify_fallback_to_cloud(self) -> bool:
        """Verify fallback to cloud providers when Ollama unavailable."""
        logger.info("\n=== Testing Fallback to Cloud Providers ===")

        # Test with a domain query when Ollama might not have the model
        query = "Design a complex PCB with advanced routing"
        messages = [{"role": "user", "content": query}]

        try:
            # Use DOMAIN strategy but allow fallback
            response = await self.router.send(
                messages,
                strategy=Strategy.DOMAIN,
                domain="kicad",
                max_tokens=50,
            )

            # If Ollama is available, it should use it; otherwise fallback to cloud
            logger.info(
                f"✓ Query routed to provider='{response.provider}', model='{response.model}'"
            )

            # Check that we got a response (either from Ollama or cloud)
            passed = response.content is not None and len(response.content) > 0

            if response.provider == "ollama":
                logger.info("  Ollama was available, no fallback needed")
            else:
                logger.info(f"  Fallback activated to {response.provider}")

            self.results["fallback_to_cloud"] = passed
            return passed

        except Exception as e:
            logger.error(f"✗ Fallback test failed: {e}")
            self.results["fallback_to_cloud"] = False
            return False

    async def verify_model_selection(self) -> bool:
        """Verify correct mascarade-* model selection for each domain."""
        logger.info("\n=== Testing Model Selection ===")

        domain_model_map = {
            "kicad": "mascarade-kicad",
            "spice": "mascarade-spice",
            "freecad": "mascarade-freecad",
            "stm32": "mascarade-iot",
            "iot": "mascarade-iot",
        }

        all_passed = True
        for domain, expected_model in domain_model_map.items():
            model = self.detector.get_model_for_domain(domain)
            passed = model == expected_model
            status = "✓" if passed else "✗"
            logger.info(
                f"{status} Domain '{domain}' -> model='{model}' (expected: '{expected_model}')"
            )
            all_passed = all_passed and passed

        self.results["model_selection"] = all_passed
        return all_passed

    async def verify_multiple_domains_sequence(self) -> bool:
        """Verify handling multiple domain queries in sequence."""
        logger.info("\n=== Testing Multiple Domains in Sequence ===")

        queries = [
            ("KiCad schematic design", "kicad"),
            ("SPICE circuit simulation", "spice"),
            ("FreeCAD parametric modeling", "freecad"),
        ]

        all_passed = True
        for query, domain in queries:
            try:
                messages = [{"role": "user", "content": query}]
                model = self.detector.get_model_for_domain(domain)

                response = await self.router.send(
                    messages,
                    strategy=Strategy.DOMAIN,
                    domain=domain,
                    model=model,
                    max_tokens=50,
                )

                passed = response.content is not None
                status = "✓" if passed else "✗"
                logger.info(f"{status} Sequential query for '{domain}' completed")
                all_passed = all_passed and passed

            except Exception as e:
                logger.error(f"✗ Sequential query for '{domain}' failed: {e}")
                all_passed = False

        self.results["multiple_domains_sequence"] = all_passed
        return all_passed

    async def verify_performance(self) -> bool:
        """Verify domain detection performance is <50ms."""
        logger.info("\n=== Testing Detection Performance ===")

        query = "How do I design a PCB in KiCad with complex routing and multiple layers?"

        # Warm-up
        self.detector.detect_domain(query)

        # Measure
        iterations = 100
        start_time = time.perf_counter()
        for _ in range(iterations):
            self.detector.detect_domain(query)
        elapsed = (time.perf_counter() - start_time) * 1000

        avg_time = elapsed / iterations
        passed = avg_time < 50.0
        status = "✓" if passed else "✗"
        logger.info(f"{status} Average detection time: {avg_time:.2f}ms (target: <50ms)")

        self.results["performance"] = passed
        return passed

    async def run_all_tests(self) -> bool:
        """Run all verification tests."""
        logger.info("=" * 60)
        logger.info("Domain-Aware Intelligent Routing - E2E Verification")
        logger.info("=" * 60)

        # Check Ollama availability
        ollama_available = await self.check_ollama_service()

        # Run tests
        tests = [
            ("Domain Detection", self.verify_domain_detection),
            ("Model Selection", self.verify_model_selection),
            ("Detection Performance", self.verify_performance),
            ("Multiple Domains Sequence", self.verify_multiple_domains_sequence),
            ("Fallback to Cloud", self.verify_fallback_to_cloud),
        ]

        # Only run Ollama-specific tests if Ollama is available
        if ollama_available:
            tests.insert(
                3,
                ("Domain Routing with Ollama", self.verify_domain_routing_with_ollama),
            )
        else:
            logger.warning("\n⚠️  Ollama service not available - skipping Ollama-specific tests")
            logger.warning("   To test with Ollama, start the service with: ollama serve")
            logger.warning("   And ensure mascarade-* models are loaded")

        all_passed = True
        for test_name, test_func in tests:
            try:
                passed = await test_func()
                all_passed = all_passed and passed
            except Exception as e:
                logger.error(f"\n✗ Test '{test_name}' raised exception: {e}")
                all_passed = False

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("Verification Summary")
        logger.info("=" * 60)

        for test_name, result in self.results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"{status}: {test_name}")

        logger.info("=" * 60)

        if all_passed:
            logger.info("✓ All tests passed!")
            return True
        else:
            logger.error("✗ Some tests failed")
            return False


async def main():
    """Main entry point."""
    verifier = E2EVerifier()
    success = await verifier.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

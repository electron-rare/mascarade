#!/usr/bin/env python3
"""Profile Mascarade Router startup to identify slow providers."""

import importlib
import sys
import time
from pathlib import Path

# Add core to path
core_dir = Path(__file__).resolve().parent.parent / "core"
sys.path.insert(0, str(core_dir))

# Suppress noisy logs during profiling
import logging

logging.basicConfig(level=logging.WARNING)


def time_import(module_name: str, class_name: str) -> tuple[float, float, bool, str | None]:
    """Time importing and initializing a provider.

    Returns (import_time, init_time, is_configured, error).
    """
    error = None

    # Time import
    t0 = time.perf_counter()
    try:
        module = importlib.import_module(module_name)
        provider_cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        return time.perf_counter() - t0, 0.0, False, f"import error: {exc}"
    import_time = time.perf_counter() - t0

    # Time init
    t1 = time.perf_counter()
    try:
        provider = provider_cls()
        configured = provider.is_configured
    except Exception as exc:
        return import_time, time.perf_counter() - t1, False, f"init error: {exc}"
    init_time = time.perf_counter() - t1

    return import_time, init_time, configured, error


def main() -> None:
    provider_specs = [
        ("mascarade.router.providers.claude", "ClaudeProvider"),
        ("mascarade.router.providers.openai", "OpenAIProvider"),
        ("mascarade.router.providers.mistral", "MistralProvider"),
        ("mascarade.router.providers.mistral_agents", "MistralAgentsProvider"),
        ("mascarade.router.providers.bedrock", "BedrockProvider"),
        ("mascarade.router.providers.google", "GoogleProvider"),
        ("mascarade.router.providers.huggingface", "HuggingFaceProvider"),
        ("mascarade.router.providers.ollama", "OllamaProvider"),
        ("mascarade.router.providers.exo", "ExoProvider"),
        ("mascarade.router.providers.llama_cpp", "LlamaCppProvider"),
        ("mascarade.router.providers.mlx_lm", "MLXLMProvider"),
        ("mascarade.router.providers.apple_coreml", "AppleCoreMLProvider"),
        ("mascarade.router.providers.litellm", "LiteLLMProvider"),
        ("mascarade.router.providers.codestral", "CodestralProvider"),
        ("mascarade.router.providers.github_copilot", "GitHubCopilotProvider"),
        ("mascarade.router.providers.litellm_universal", "LiteLLMUniversalProvider"),
    ]

    print("=" * 76)
    print("Mascarade Router — Startup Profile")
    print("=" * 76)

    results = []
    total_start = time.perf_counter()

    for module_name, class_name in provider_specs:
        import_t, init_t, configured, error = time_import(module_name, class_name)
        total_t = import_t + init_t
        results.append({
            "name": class_name,
            "module": module_name,
            "import_time": import_t,
            "init_time": init_t,
            "total_time": total_t,
            "configured": configured,
            "error": error,
        })

    total_elapsed = time.perf_counter() - total_start

    # Sort by total time descending
    results.sort(key=lambda r: r["total_time"], reverse=True)

    # Print table
    print(f"\n{'Provider':<30} {'Import':>8} {'Init':>8} {'Total':>8} {'Status':<12}")
    print("-" * 76)
    for r in results:
        status = "configured" if r["configured"] else (r["error"] or "not configured")
        # Truncate status
        if len(status) > 30:
            status = status[:27] + "..."
        print(
            f"{r['name']:<30} {r['import_time']*1000:>7.1f}ms {r['init_time']*1000:>7.1f}ms "
            f"{r['total_time']*1000:>7.1f}ms {status}"
        )

    print("-" * 76)
    print(f"{'TOTAL':<30} {'':<8} {'':<8} {total_elapsed*1000:>7.1f}ms")

    # Identify slow providers (> 100ms)
    slow = [r for r in results if r["total_time"] > 0.1]
    if slow:
        print(f"\n{'=' * 76}")
        print("SLOW PROVIDERS (> 100ms):")
        print(f"{'=' * 76}")
        for r in slow:
            phase = "import" if r["import_time"] > r["init_time"] else "init"
            print(f"  - {r['name']}: {r['total_time']*1000:.0f}ms (bottleneck: {phase})")

    # Suggestions
    print(f"\n{'=' * 76}")
    print("OPTIMIZATION SUGGESTIONS:")
    print(f"{'=' * 76}")

    slow_imports = [r for r in results if r["import_time"] > 0.05]
    if slow_imports:
        print("\n1. LAZY IMPORTS — These providers have slow imports (> 50ms):")
        for r in slow_imports:
            print(f"   - {r['name']} ({r['import_time']*1000:.0f}ms import)")
        print("   -> Move their import into a lazy wrapper in _register_defaults()")
        print("   -> Only import when actually needed (is_configured check)")

    slow_inits = [r for r in results if r["init_time"] > 0.05]
    if slow_inits:
        print("\n2. PARALLEL INIT — These providers have slow initialization (> 50ms):")
        for r in slow_inits:
            print(f"   - {r['name']} ({r['init_time']*1000:.0f}ms init)")
        print("   -> Consider async/threaded initialization")

    unconfigured = [r for r in results if not r["configured"] and not r["error"]]
    if unconfigured:
        print(f"\n3. SKIP UNCONFIGURED — {len(unconfigured)} providers are not configured:")
        for r in unconfigured:
            print(f"   - {r['name']}")
        print("   -> Add a lightweight pre-check (env var presence) before importing")

    configured_count = sum(1 for r in results if r["configured"])
    error_count = sum(1 for r in results if r["error"])
    print(f"\nSummary: {configured_count} configured, "
          f"{len(unconfigured)} unconfigured, {error_count} errors, "
          f"{total_elapsed*1000:.0f}ms total")


if __name__ == "__main__":
    main()

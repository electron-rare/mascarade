#!/usr/bin/env python3
"""
End-to-end verification script for cost tracking feature.

This script verifies:
1. Analytics modules can be imported
2. ClickHouse connection works
3. Prometheus metrics are registered
4. Cost calculator works correctly
5. Router integration is properly configured
"""

import sys
import os

# Add core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

def verify_imports():
    """Verify all analytics modules can be imported."""
    print("=" * 60)
    print("STEP 1: Verifying module imports")
    print("=" * 60)

    try:
        from mascarade.analytics.clickhouse_logger import CostEventLogger, get_cost_logger
        print("✅ ClickHouse logger module imported")
    except Exception as e:
        print(f"❌ Failed to import ClickHouse logger: {e}")
        return False

    try:
        from mascarade.analytics.prometheus_metrics import COST_METRICS
        print("✅ Prometheus metrics module imported")
    except Exception as e:
        print(f"❌ Failed to import Prometheus metrics: {e}")
        return False

    try:
        from mascarade.analytics.cost_calculator import get_cost_calculator, CostCalculator
        print("✅ Cost calculator module imported")
    except Exception as e:
        print(f"❌ Failed to import cost calculator: {e}")
        return False

    return True


def verify_cost_calculator():
    """Verify cost calculator functionality."""
    print("\n" + "=" * 60)
    print("STEP 2: Verifying cost calculator")
    print("=" * 60)

    try:
        from mascarade.analytics.cost_calculator import get_cost_calculator

        calc = get_cost_calculator()
        print("✅ Cost calculator instance created")

        # Test cost calculation
        calc.register_provider_pricing("test_provider", 10.0, 20.0)
        cost = calc.calculate_cost("test_provider", None, 1000, 500)
        expected = (1000 * 10.0 + 500 * 20.0) / 1_000_000

        if abs(cost - expected) < 0.0001:
            print(f"✅ Cost calculation correct: ${cost:.6f}")
        else:
            print(f"❌ Cost calculation incorrect: got ${cost:.6f}, expected ${expected:.6f}")
            return False

        # Test singleton pattern
        calc2 = get_cost_calculator()
        if calc is calc2:
            print("✅ Singleton pattern working")
        else:
            print("❌ Singleton pattern broken")
            return False

        return True
    except Exception as e:
        print(f"❌ Cost calculator verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_router_integration():
    """Verify router has cost tracking integrated."""
    print("\n" + "=" * 60)
    print("STEP 3: Verifying router integration")
    print("=" * 60)

    try:
        from mascarade.router.router import Router

        router = Router()

        # Check cost_logger attribute
        if hasattr(router, 'cost_logger'):
            print("✅ Router has cost_logger attribute")
        else:
            print("❌ Router missing cost_logger attribute")
            return False

        # Check cost_calculator attribute
        if hasattr(router, 'cost_calculator'):
            print("✅ Router has cost_calculator attribute")
        else:
            print("❌ Router missing cost_calculator attribute")
            return False

        # Check _get_effective_cost method exists
        if hasattr(router, '_get_effective_cost'):
            print("✅ Router has _get_effective_cost method")
        else:
            print("❌ Router missing _get_effective_cost method")
            return False

        return True
    except Exception as e:
        print(f"❌ Router integration verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_clickhouse_table():
    """Verify ClickHouse table exists with correct schema."""
    print("\n" + "=" * 60)
    print("STEP 4: Verifying ClickHouse schema")
    print("=" * 60)

    try:
        import subprocess
        result = subprocess.run(
            ['docker', 'compose', 'exec', '-T', 'clickhouse', 'clickhouse-client',
             '--query', 'DESCRIBE mascarade.cost_events'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            print("✅ ClickHouse cost_events table exists")

            # Check for required columns
            required_columns = [
                'timestamp', 'provider', 'model', 'agent',
                'input_tokens', 'output_tokens', 'cost',
                'strategy', 'success'
            ]

            output = result.stdout
            missing = [col for col in required_columns if col not in output]

            if not missing:
                print("✅ All required columns present")
                print(f"   Schema:\n{output}")
                return True
            else:
                print(f"❌ Missing columns: {missing}")
                return False
        else:
            print(f"❌ Failed to query ClickHouse: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ ClickHouse verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_server_endpoints():
    """Verify server has the required endpoints."""
    print("\n" + "=" * 60)
    print("STEP 5: Verifying server endpoints")
    print("=" * 60)

    try:
        # Read server.py and check for endpoints
        server_path = os.path.join(os.path.dirname(__file__), 'core', 'mascarade', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()

        if '/v1/analytics/cost' in content:
            print("✅ /v1/analytics/cost endpoint defined")
        else:
            print("❌ /v1/analytics/cost endpoint missing")
            return False

        if '@app.get("/metrics")' in content or '@app.get(\'/metrics\')' in content:
            print("✅ /metrics endpoint defined")
        else:
            print("❌ /metrics endpoint missing")
            return False

        return True
    except Exception as e:
        print(f"❌ Server endpoint verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_prometheus_config():
    """Verify Prometheus configuration includes mascarade-core."""
    print("\n" + "=" * 60)
    print("STEP 6: Verifying Prometheus configuration")
    print("=" * 60)

    try:
        prom_config = os.path.join(
            os.path.dirname(__file__),
            'deploy', 'prometheus', 'prometheus.yml'
        )

        with open(prom_config, 'r') as f:
            content = f.read()

        if 'mascarade-core' in content and '/metrics' in content:
            print("✅ Prometheus configured to scrape mascarade-core")
            return True
        else:
            print("❌ Prometheus not configured for mascarade-core")
            return False
    except Exception as e:
        print(f"❌ Prometheus config verification failed: {e}")
        return False


def verify_grafana_dashboard():
    """Verify Grafana dashboard exists."""
    print("\n" + "=" * 60)
    print("STEP 7: Verifying Grafana dashboard")
    print("=" * 60)

    try:
        dashboard_path = os.path.join(
            os.path.dirname(__file__),
            'deploy', 'grafana', 'provisioning', 'dashboards', 'json',
            'mascarade-cost-tracking.json'
        )

        if os.path.exists(dashboard_path):
            print(f"✅ Dashboard file exists: {dashboard_path}")

            # Check if it's valid JSON and has the right structure
            import json
            with open(dashboard_path, 'r') as f:
                dashboard = json.load(f)

            if dashboard.get('title') == 'Mascarade Cost Tracking':
                print("✅ Dashboard has correct title")
            else:
                print(f"❌ Dashboard title incorrect: {dashboard.get('title')}")
                return False

            panels = dashboard.get('panels', [])
            if len(panels) > 0:
                print(f"✅ Dashboard has {len(panels)} panels")
            else:
                print("❌ Dashboard has no panels")
                return False

            return True
        else:
            print(f"❌ Dashboard file not found: {dashboard_path}")
            return False
    except Exception as e:
        print(f"❌ Grafana dashboard verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification steps."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "COST TRACKING E2E VERIFICATION" + " " * 17 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    results = {
        'Module Imports': verify_imports(),
        'Cost Calculator': verify_cost_calculator(),
        'Router Integration': verify_router_integration(),
        'ClickHouse Schema': verify_clickhouse_table(),
        'Server Endpoints': verify_server_endpoints(),
        'Prometheus Config': verify_prometheus_config(),
        'Grafana Dashboard': verify_grafana_dashboard(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    for step, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{step:.<40} {status}")

    all_passed = all(results.values())

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL VERIFICATION STEPS PASSED!")
        print("=" * 60)
        print("\nThe cost tracking feature is ready for testing.")
        print("\nNext steps:")
        print("  1. Fix the core service build issue (fastecdsa dependency)")
        print("  2. Start services: docker compose up core prometheus grafana -d")
        print("  3. Send test LLM request via Router")
        print("  4. Verify metrics at: http://localhost:8100/metrics")
        print("  5. View analytics at: http://localhost:8100/v1/analytics/cost")
        print("  6. View dashboard at: http://localhost:3000/dashboards")
        return 0
    else:
        print("❌ SOME VERIFICATION STEPS FAILED")
        print("=" * 60)
        failed = [step for step, passed in results.items() if not passed]
        print(f"\nFailed steps: {', '.join(failed)}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

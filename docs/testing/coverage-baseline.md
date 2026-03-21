# Coverage Baseline Report

**Generated:** 2026-03-16
**Service:** core
**Tool:** pytest-cov

## Summary

| Metric | Value |
|--------|-------|
| **Total Coverage** | **45%** |
| Total Statements | 11,833 |
| Missing | 6,038 |
| Branches | 3,000 |
| Partial | 308 |

## Test Results

- **Passed:** 468 tests
- **Failed:** 247 tests
- **Errors:** 33 tests
- **Warnings:** 10

## Coverage Report Location

The detailed HTML coverage report is available at:
```
core/htmlcov/index.html
```

## How to Regenerate

To regenerate this coverage report, run:

```bash
cd core
python -m pytest --cov=mascarade --cov-report=html --cov-report=term
```

Or use the verification command:
```bash
cd core && python -m pytest --cov=mascarade --cov-report=html && echo 'Coverage report generated'
```

## Notes

- This is the baseline coverage established during the P2 testing phase
- Many tests are failing due to missing dependencies or configuration issues
- The 45% coverage represents the current state before improvements
- P2P tests are failing with permission errors (networking)
- Several tests have AttributeError issues with SecretStr objects
- ComfyUI tests are failing due to SOCKS proxy import issues

## Next Steps

1. Fix failing tests to improve reliability
2. Increase coverage by adding tests for uncovered modules
3. Target: Achieve >80% coverage for critical modules
4. Focus on:
   - Router components
   - Provider implementations
   - Agent orchestration
   - API endpoints

# Router Module Audit (2026-03-11)
## 23 issues: 3 CRITICAL, 5 HIGH, 8 MEDIUM, 7 LOW

### CRITICAL (3)
1. Stream fallback yields partial duplicated data (router.py:328-354) — FIXED
2. Bedrock stream() blocks event loop with sync iteration (bedrock.py:205-209) — FIXED
3. Google stream() blocks event loop with sync iteration (google.py:279-283) — FIXED

### HIGH (5)
4. response_format silently dropped for most providers — FIXED by Tower Claude
5. send() signature diverges from base class — FIXED by Tower Claude
6. httpx clients never closed (resource leak) — FIXED by Tower Claude (Router.close())
7. Bedrock TOCTOU race in lazy client init — TODO
8. response.usage passed directly instead of safe variable — FIXED

### MEDIUM (8)
9-10. stream() missing @_retry (claude, openai) — FIXED by Tower Claude
11. Fallback sequence can produce duplicates — TODO
12. Failure stats never used for routing — FIXED by Tower Claude (fallback deprio)
13. Google messages flattened to text — TODO
14. Bedrock system role coerced to user — TODO
15. Sync HTTP in available_models() — TODO
16. Cheapest strategy sums costs naively — TODO

### LOW (7)
17-23. Import-time settings, sys.path, fake streaming, etc.

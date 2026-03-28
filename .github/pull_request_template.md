## Summary

Describe the change in 3-5 lines.

## Areas Touched

- [ ] core
- [ ] api
- [ ] web
- [ ] e2e
- [ ] deploy/infra
- [ ] docs

## API Contract Impact

- [ ] No API contract change
- [ ] API contract changed (list impacted endpoints/schemas)

## Cross-Stack Coherence

- [ ] If feature is cross-stack, related core/api/web updates are in this same PR
- [ ] API and UI expectations are aligned
- [ ] Backward compatibility validated or migration documented

## Validation Executed

List commands executed.

```bash
cd core && python -m pytest
cd core && ruff check mascarade/ tests/
cd core && mypy mascarade/
cd api && npm run build && npm test
cd web && npm run build && npm test -- --run
```

## Risk and Rollback

- Risk level: low / medium / high
- Rollback plan:
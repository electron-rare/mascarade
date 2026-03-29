---
description: "Generate a complete frontend feature scaffold aligned with Mascarade React bridge conventions and API boundaries."
name: "frontend-feature-scaffold"
argument-hint: "Feature name + user story + route + API endpoints"
agent: "agent"
---

Build a complete frontend feature scaffold for `web/` using the repository conventions.

## Inputs

- Feature name: ${input:FeatureName}
- User story: ${input:UserStory}
- Route path: ${input:RoutePath}
- API endpoints used: ${input:ApiEndpoints}
- States required: ${input:States}

## Requirements

1. Follow workspace instructions and web-specific instruction files.
2. Keep strict TypeScript typing (no `any`).
3. Use existing API abstraction/hook patterns (`useApi` / `useFetch`).
4. Respect boundary `web -> api -> core` (no direct core calls).
5. Include responsive + accessibility considerations.
6. Add tests for happy path and API error path.

## Output format

Return exactly these sections:

1. File plan
- List files to create/update under `web/src/`.

2. Implementation
- Provide complete code for each file.

3. Test plan
- Unit/component tests to add.
- Smoke checks to run manually.

4. Validation commands
- Commands to run for `web` and, if needed, `api`.

## Repo references

- [.github/instructions/web-react.instructions.md](../instructions/web-react.instructions.md)
- [.github/instructions/frontend-testing.instructions.md](../instructions/frontend-testing.instructions.md)
- [web/src/api/client.ts](../../web/src/api/client.ts)
- [web/src/hooks/useApi.ts](../../web/src/hooks/useApi.ts)
- [web/src/hooks/useFetch.ts](../../web/src/hooks/useFetch.ts)
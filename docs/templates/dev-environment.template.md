---
title: Dev Environment Guide Template
version: 1
audience: engineers
---

# Development Environment Guide

## 1. Project Overview

- Project name: <PROJECT_NAME>
- Stacks: <STACK_1>, <STACK_2>, <STACK_3>
- Local ports: <PORT_MAP>

## 2. Toolchain Requirements

- Python: <VERSION_OR_NA>
- Node.js: <VERSION_OR_NA>
- Package manager: <npm|pnpm|poetry|pip>
- Docker: <REQUIRED_OR_OPTIONAL>

## 3. Initial Setup

```bash
git clone <REPO_URL>
cd <REPO_DIR>
<INSTALL_COMMANDS>
```

## 4. Environment Variables

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| <VAR_NAME> | yes/no | <VALUE> | <DESCRIPTION> |

## 5. Run Locally

```bash
<RUN_COMMAND>
```

## 6. Validation

```bash
<BUILD_COMMAND>
<TEST_COMMAND>
<LINT_COMMAND>
```

## 7. Common Issues

### Issue: <NAME>
- Symptom: <SYMPTOM>
- Cause: <CAUSE>
- Fix:

```bash
<FIX_COMMAND>
```

## 8. References

- <DOC_LINK_1>
- <DOC_LINK_2>
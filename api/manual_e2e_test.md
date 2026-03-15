# Manual E2E Verification Guide

This guide shows how to manually verify the Pipeline API endpoints work end-to-end.

## Prerequisites

1. Start the API server:
   ```bash
   cd api
   npm run build
   node dist/index.js
   ```

2. In a new terminal, run the following tests:

## Test 1: POST /api/pipeline/run (dry-run mode)

```bash
curl -X POST http://localhost:3000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"domain":"stm32","dry_run":true}'
```

**Expected Response:**
```json
{
  "status": "started",
  "run_id": "pipeline-stm32-<timestamp>",
  "domain": "stm32",
  "dry_run": true
}
```

## Test 2: GET /api/pipeline/status

Wait 2-3 seconds after triggering the pipeline, then:

```bash
curl http://localhost:3000/api/pipeline/status
```

**Expected Response (if pipeline ran):**
```json
{
  "ok": true,
  "status": "active",
  "data": {
    "domain": "stm32",
    "base_model": "...",
    "completed_steps": ["train", "merge", ...],
    "last_updated": "..."
  }
}
```

**Expected Response (if no pipeline has run):**
```json
{
  "ok": true,
  "status": "idle",
  "message": "No pipeline has been run yet"
}
```

## Test 3: GET /api/pipeline/models

```bash
curl http://localhost:3000/api/pipeline/models
```

**Expected Response:**
```json
{
  "ok": true,
  "status": "success",
  "data": {
    "version": 1,
    "models": {
      "model_id": {
        "domain": "...",
        "training_info": { ... },
        "artifacts": { ... }
      }
    }
  }
}
```

Or if no models registered:
```json
{
  "ok": true,
  "status": "empty",
  "message": "No models have been registered yet",
  "data": { "version": 1, "models": {} }
}
```

## Test 4: Invalid Domain Handling

```bash
curl -X POST http://localhost:3000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"domain":"invalid","dry_run":true}'
```

**Expected Response (400 error):**
```json
{
  "error": "Invalid or missing domain parameter",
  "valid_domains": ["stm32", "spice", "iot", ...]
}
```

## Automated Test Results

The automated E2E test script (`test_e2e_pipeline.sh`) has verified all endpoints:

✅ **Test 1:** POST /api/pipeline/run - Returns 200 with run_id
✅ **Test 2:** GET /api/pipeline/status - Returns 200 with ok:true
✅ **Test 3:** GET /api/pipeline/models - Returns 200 with data field
✅ **Test 4:** Invalid domain handling - Returns 400 with error message

All 4 tests passed successfully!

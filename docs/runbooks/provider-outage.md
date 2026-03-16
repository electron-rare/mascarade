# Provider Outage Runbook

Date: 2026-03-16

## Overview

This runbook covers handling LLM provider outages in the Mascarade orchestration system.
Mascarade routes requests to multiple LLM providers (OpenAI, Anthropic, Mistral, Ollama, etc.)
through a unified router with fallback capabilities.

## Symptoms

### User-Facing
- Agent responses timing out or returning 5xx errors
- API returning `provider_unavailable` or `all_providers_failed` errors
- Increased latency for agent completions
- Dashboard showing degraded provider health status

### System-Level
- Router logs showing repeated connection failures to specific provider
- Health check endpoints returning failures for provider services
- Prometheus metrics showing spike in provider error rates
- Ops console displaying red status for provider availability

### Log Patterns
```
ERROR: Provider anthropic failed after 3 retries: ConnectionError
WARNING: Falling back to provider mistral after anthropic failure
ERROR: All providers exhausted for agent request
```

## Diagnosis

### Step 1: Verify Provider Status
Check external provider status pages:
- OpenAI: https://status.openai.com
- Anthropic: https://status.anthropic.com
- Mistral: https://status.mistral.ai

### Step 2: Check Local Connectivity
```bash
cd /mascarade
# Test provider health endpoints
curl -fsS http://127.0.0.1:8100/health
curl -fsS http://127.0.0.1:3100/health

# Check provider-specific health
curl -X POST http://127.0.0.1:8100/router/test \
  -H "Content-Type: application/json" \
  -d '{"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"}'
```

### Step 3: Review Router Logs
```bash
cd /mascarade
docker compose logs -f --tail 200 core | grep -i "provider\|error"
```

### Step 4: Check Provider Configuration
```bash
cd /mascarade
# Verify API keys are set
grep -E "OPENAI_API_KEY|ANTHROPIC_API_KEY|MISTRAL_API_KEY" .env
# Check if keys are valid (non-empty, not placeholder)
```

### Step 5: Identify Impacted Provider
```bash
cd /mascarade
# Review recent router decisions
docker compose logs core --since 10m | grep "ProviderRouter"
```

## Remediation

### Immediate Actions (First 5 Minutes)

#### 1. Enable Fallback Routing
Ensure router is configured for automatic fallback:
```bash
cd /mascarade
# Check router strategy in core config
docker compose exec core cat /app/core/mascarade/router/config.py | grep -A5 "strategy"
```

If not configured, router should automatically fall back per provider priority.

#### 2. Force Provider Switch (Manual Override)
If a specific provider is down, route traffic to alternatives:
```bash
cd /mascarade
# Temporarily disable failed provider via environment override
docker compose exec core sh -c 'export DISABLE_PROVIDER_ANTHROPIC=true && supervisorctl restart core-service'
```

#### 3. Monitor Fallback Success
```bash
cd /mascarade
docker compose logs -f core | grep "Routing to provider"
# Verify requests are succeeding with fallback provider
```

### Short-Term Actions (Next 30 Minutes)

#### 4. Update Router Strategy
If a provider is experiencing extended outage, update routing preferences:

```python
# In core/mascarade/router/config.py or via environment
PROVIDER_PRIORITY = [
    "mistral",      # Move working provider to top
    "openai",
    "anthropic",    # Demote failing provider
    "ollama",
]
```

Then restart:
```bash
cd /mascarade
docker compose restart core
```

#### 5. Increase Timeout/Retry Settings
```bash
cd /mascarade
# Increase retry attempts and timeout for transient issues
echo "ROUTER_MAX_RETRIES=5" >> .env
echo "ROUTER_TIMEOUT_SECONDS=60" >> .env
docker compose up -d core
```

#### 6. Switch to Local Ollama
For critical operations, route to local Ollama instance:
```bash
cd /mascarade
# Ensure Ollama is running
docker compose ps ollama
curl -fsS http://127.0.0.1:11434/api/tags

# Update agent requests to prefer local provider
# POST /api/agents/send with "provider": "ollama"
```

### Recovery Verification

```bash
cd /mascarade
# Test agent request end-to-end
curl -X POST http://127.0.0.1:3100/api/agents/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${MASCARADE_API_KEY}" \
  -d '{
    "agent": "general",
    "message": "Test routing after provider recovery",
    "provider": "auto"
  }'

# Verify response is successful
# Check which provider was used in response headers or logs
```

## Prevention

### 1. Multi-Provider Configuration
Ensure `.env` has multiple provider keys configured:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...
OLLAMA_HOST=http://ollama:11434
```

### 2. Implement Circuit Breaker
Update router to implement circuit breaker pattern:
- Track failure rates per provider
- Automatically disable provider after threshold failures
- Auto-recover after cooldown period

### 3. Monitoring & Alerting
Set up proactive monitoring:
```bash
cd /mascarade
# Enable ops-console for live monitoring
./setup --with core,api,ops-console,ollama --yes

# Access dashboard at http://127.0.0.1:3100/metrics
# Configure alerts for provider failure thresholds
```

### 4. Provider Health Checks
Implement periodic health checks:
```bash
cd /mascarade
# Add to crontab for automated health monitoring
crontab -e
# */5 * * * * /mascarade/scripts/provider_health_check.sh
```

### 5. Local Model Redundancy
Ensure critical models are available locally via Ollama:
```bash
cd /mascarade
# Pull backup models
docker compose exec ollama ollama pull qwen2.5:14b
docker compose exec ollama ollama pull mistral:latest
docker compose exec ollama ollama pull llama3.2:latest

# Verify local models
docker compose exec ollama ollama list
```

### 6. Request Rate Limiting
Configure rate limits to prevent provider quota exhaustion:
```bash
cd /mascarade
echo "ROUTER_RATE_LIMIT_PER_MINUTE=60" >> .env
echo "ROUTER_RATE_LIMIT_PER_PROVIDER=20" >> .env
docker compose up -d core
```

### 7. Documentation & Runbook Updates
Keep this runbook updated with:
- Provider-specific outage patterns
- Mean time to recovery (MTTR) data
- Post-mortem learnings

## Escalation

### When to Escalate
- All providers down for > 15 minutes
- Ollama fallback also failing
- Critical agent workflows blocked
- Data loss or corruption suspected

### Escalation Path
1. Check provider status pages and community forums
2. Review Mascarade GitHub issues for known problems
3. Contact provider support (for extended outages)
4. Document incident in ops log

## Related Documentation
- Router architecture: `core/mascarade/router/README.md`
- Provider implementations: `core/mascarade/router/providers/`
- Ops console guide: `docs/RUNBOOK_VM_OPS.md`
- Multi-machine execution: `docs/MULTI_MACHINE_EXECUTION.md`

## Post-Incident Review

After resolution:
1. Document outage duration and impact
2. Review which providers failed and fallback success rate
3. Update routing priorities based on reliability data
4. Consider adding redundant providers if single point of failure identified
5. Update monitoring thresholds to catch similar issues earlier

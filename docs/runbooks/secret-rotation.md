# Secret Rotation Runbook

Date: 2026-03-16

## Overview

This runbook covers the secure rotation of secrets and API keys in the Mascarade orchestration system.
Secrets include LLM provider API keys, database credentials, internal API keys, and service tokens.
Regular rotation minimizes exposure risk and follows security best practices.

## Symptoms

### Scheduled Rotation (Proactive)
- Quarterly/monthly rotation schedule due
- Security audit recommendation
- Team member departure requiring key revocation
- Compliance requirement for periodic rotation

### Emergency Rotation (Reactive)
- API key leaked in logs or public repository
- Unauthorized access detected
- Provider notifying of potential compromise
- Failed authentication attempts in logs
- Key included in error messages or debug output

### Log Patterns (Indicating Key Issues)
```
ERROR: Authentication failed: Invalid API key
WARNING: API key rate limit exceeded (possible key sharing)
ERROR: 401 Unauthorized: Check API credentials
WARNING: Multiple failed authentication attempts from unknown IP
```

## Diagnosis

### Step 1: Identify Which Secrets Need Rotation
```bash
cd /mascarade
# List all secrets in .env
grep -E "_KEY|_SECRET|_TOKEN|_PASSWORD" .env | sed 's/=.*/=***/'

# Common secrets to rotate:
# - MASCARADE_API_KEY
# - OPENAI_API_KEY
# - ANTHROPIC_API_KEY
# - MISTRAL_API_KEY
# - POSTGRES_PASSWORD
# - NOTION_API_KEY (if used)
# - KILL_LIFE_GITHUB_TOKEN (if used)
# - DIFY_SECRET_KEY (on photon-machine)
```

### Step 2: Check Current Key Usage
```bash
cd /mascarade
# Review which services are actively using keys
docker compose ps

# Check logs for authentication events
docker compose logs --since 24h | grep -i "auth\|api.key\|secret"

# Verify provider connectivity
curl -X POST http://127.0.0.1:8100/router/test \
  -H "Content-Type: application/json" \
  -d '{"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"}'
```

### Step 3: Identify if Compromise Occurred
```bash
cd /mascarade
# Check for suspicious activity in logs
docker compose logs --since 7d | grep -i "unauthorized\|forbidden\|invalid.*key"

# Review API usage patterns for anomalies
# - Unexpected geographic locations
# - Unusual request volumes
# - Failed authentication attempts

# Check provider dashboards:
# - OpenAI: https://platform.openai.com/usage
# - Anthropic: https://console.anthropic.com/settings/usage
# - Mistral: https://console.mistral.ai/usage
```

### Step 4: Determine Rotation Scope
```bash
# Full rotation needed if:
# - Keys potentially compromised
# - Compliance-mandated rotation period
# - Team member with key access departed

# Partial rotation acceptable if:
# - Single provider key expired
# - Proactive security hardening
# - Testing new provider
```

## Remediation

### Pre-Rotation Checklist
- [ ] Backup current .env file
- [ ] Document all services using secrets
- [ ] Prepare new secrets/keys in advance
- [ ] Schedule maintenance window if needed
- [ ] Notify stakeholders of potential brief downtime

### Step 1: Backup Current Configuration
```bash
cd /mascarade
# Backup .env securely
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
chmod 600 .env.backup.*

# Backup .env.machine.local if on photon-machine
if [ -f .env.machine.local ]; then
  cp .env.machine.local .env.machine.local.backup.$(date +%Y%m%d_%H%M%S)
  chmod 600 .env.machine.local.backup.*
fi

# Store backups securely (not in git)
mv .env.backup.* ~/.mascarade-secrets-backup/
```

### Step 2: Generate New Secrets

#### Internal API Key (MASCARADE_API_KEY)
```bash
cd /mascarade
# Generate strong random key
NEW_MASCARADE_KEY=$(openssl rand -base64 32)
echo "New MASCARADE_API_KEY: $NEW_MASCARADE_KEY"

# Update .env
sed -i.bak "s/^MASCARADE_API_KEY=.*/MASCARADE_API_KEY=${NEW_MASCARADE_KEY}/" .env
```

#### Database Password (POSTGRES_PASSWORD)
```bash
cd /mascarade
# Generate strong password
NEW_DB_PASSWORD=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
echo "New POSTGRES_PASSWORD: $NEW_DB_PASSWORD"

# Update .env
sed -i.bak "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${NEW_DB_PASSWORD}/" .env

# Update DATABASE_URL to match
# Format: postgresql://user:password@host:port/database
sed -i.bak "s/POSTGRES_PASSWORD=[^@]*/POSTGRES_PASSWORD=${NEW_DB_PASSWORD}/" .env
```

### Step 3: Rotate Provider API Keys

#### OpenAI
```bash
# 1. Go to https://platform.openai.com/api-keys
# 2. Create new secret key
# 3. Copy the key (shown only once!)
# 4. Update .env

cd /mascarade
read -sp "Enter new OpenAI API key: " NEW_OPENAI_KEY
echo
sed -i.bak "s/^OPENAI_API_KEY=.*/OPENAI_API_KEY=${NEW_OPENAI_KEY}/" .env
```

#### Anthropic
```bash
# 1. Go to https://console.anthropic.com/settings/keys
# 2. Create new API key
# 3. Copy the key
# 4. Update .env

cd /mascarade
read -sp "Enter new Anthropic API key: " NEW_ANTHROPIC_KEY
echo
sed -i.bak "s/^ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=${NEW_ANTHROPIC_KEY}/" .env
```

#### Mistral
```bash
# 1. Go to https://console.mistral.ai/api-keys
# 2. Create new API key
# 3. Copy the key
# 4. Update .env

cd /mascarade
read -sp "Enter new Mistral API key: " NEW_MISTRAL_KEY
echo
sed -i.bak "s/^MISTRAL_API_KEY=.*/MISTRAL_API_KEY=${NEW_MISTRAL_KEY}/" .env
```

### Step 4: Update Database Password (If Rotating)
```bash
cd /mascarade
# Stop services
docker compose stop core api

# Update PostgreSQL password
docker compose exec postgres psql -U mascarade -d postgres -c \
  "ALTER USER mascarade WITH PASSWORD '${NEW_DB_PASSWORD}';"

# Update .env with new password
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${NEW_DB_PASSWORD}/" .env

# Update DATABASE_URL if present
# Ensure URL matches: postgresql://mascarade:${NEW_DB_PASSWORD}@postgres:5432/mascarade
```

### Step 5: Apply New Secrets
```bash
cd /mascarade
# Verify .env syntax
cat .env | grep -E "_KEY|_SECRET|_TOKEN|_PASSWORD" | sed 's/=.*/=***/'

# Recreate containers with new secrets
docker compose down
docker compose up -d

# Wait for services to start
sleep 10
```

### Step 6: Verify New Secrets Work
```bash
cd /mascarade
# Check service health
docker compose ps

# Test internal API with new MASCARADE_API_KEY
curl -X POST http://127.0.0.1:3100/api/agents/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${NEW_MASCARADE_KEY}" \
  -d '{"agent": "general", "message": "test", "provider": "auto"}'

# Test database connectivity
docker compose exec postgres psql -U mascarade -d mascarade -c "SELECT 1;"

# Test provider API keys
curl -X POST http://127.0.0.1:8100/router/test \
  -H "Content-Type: application/json" \
  -d '{"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"}'

curl -X POST http://127.0.0.1:8100/router/test \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "model": "gpt-4"}'

curl -X POST http://127.0.0.1:8100/router/test \
  -H "Content-Type: application/json" \
  -d '{"provider": "mistral", "model": "mistral-large-latest"}'
```

### Step 7: Revoke Old Secrets
**Only after verifying new secrets work!**

#### Revoke Old Provider Keys
```bash
# OpenAI
# Go to https://platform.openai.com/api-keys
# Find old key by last 4 characters
# Click "Revoke" on old key

# Anthropic
# Go to https://console.anthropic.com/settings/keys
# Delete old key

# Mistral
# Go to https://console.mistral.ai/api-keys
# Delete old key
```

#### Clean Up Old Backup Keys
```bash
cd /mascarade
# Securely delete old .env backups after verification period (7-30 days)
# Keep one backup for emergency rollback
find ~/.mascarade-secrets-backup/ -name ".env.backup.*" -mtime +30 -exec shred -u {} \;
```

### Rollback Procedure (If Issues Occur)
```bash
cd /mascarade
# Stop services
docker compose down

# Restore previous .env
cp ~/.mascarade-secrets-backup/.env.backup.YYYYMMDD_HHMMSS .env

# Restart services
docker compose up -d

# Verify rollback successful
curl -fsS http://127.0.0.1:8100/health
curl -fsS http://127.0.0.1:3100/health
```

## Prevention

### 1. Secret Management Best Practices
```bash
cd /mascarade
# Ensure .env is in .gitignore
grep -q "^\.env$" .gitignore || echo ".env" >> .gitignore
grep -q "^\.env\..*$" .gitignore || echo ".env.*" >> .gitignore

# Set restrictive permissions
chmod 600 .env
chmod 600 .env.machine.local 2>/dev/null || true

# Never commit secrets
git log --all --full-history --source -- .env
# Should return nothing
```

### 2. Rotation Schedule
```bash
# Set up quarterly rotation reminder
cat > scripts/secret_rotation_reminder.sh << 'EOF'
#!/bin/bash
LAST_ROTATION=$(stat -f %Sm -t %Y%m%d .env.backup.* 2>/dev/null | sort | tail -1)
CURRENT_DATE=$(date +%Y%m%d)
DAYS_SINCE=$(( ($(date -jf %Y%m%d $CURRENT_DATE +%s) - $(date -jf %Y%m%d $LAST_ROTATION +%s)) / 86400 ))

if [ $DAYS_SINCE -gt 90 ]; then
  echo "WARNING: Secrets have not been rotated in $DAYS_SINCE days"
  echo "Consider rotating secrets following: docs/runbooks/secret-rotation.md"
fi
EOF

chmod +x scripts/secret_rotation_reminder.sh

# Check monthly
crontab -e
# 0 9 1 * * /mascarade/scripts/secret_rotation_reminder.sh
```

### 3. Monitoring for Leaks
```bash
cd /mascarade
# Check logs don't expose secrets
docker compose logs --since 24h | grep -E "sk-|api.*key.*=" | wc -l
# Should be 0

# Create log sanitization check
cat > scripts/check_log_leaks.sh << 'EOF'
#!/bin/bash
LEAK_COUNT=$(docker compose logs --since 24h | grep -iE "api.*key.*=|secret.*=|password.*=" | wc -l)
if [ $LEAK_COUNT -gt 0 ]; then
  echo "WARNING: Potential secret leak in logs detected!"
  echo "Review logs immediately: docker compose logs --since 24h"
fi
EOF

chmod +x scripts/check_log_leaks.sh
```

### 4. Access Control
```bash
# Limit who can access .env
cd /mascarade
chown $(whoami):$(whoami) .env
chmod 600 .env

# Audit access to .env
sudo ausearch -f .env -i 2>/dev/null || echo "Audit not configured"
```

### 5. Secret Scanning in CI/CD
```bash
# Add pre-commit hook to prevent secret commits
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Prevent committing .env or secrets
if git diff --cached --name-only | grep -q "^\.env"; then
  echo "ERROR: Attempting to commit .env file!"
  exit 1
fi

# Scan for potential API keys in staged files
if git diff --cached | grep -iE "api.*key.*=.*sk-|secret.*key.*=.*[a-zA-Z0-9]{32}"; then
  echo "ERROR: Potential API key detected in commit!"
  exit 1
fi
EOF

chmod +x .git/hooks/pre-commit
```

### 6. Automated Key Expiration
```bash
# Configure provider keys with expiration where supported
# OpenAI: Set expiration date when creating key
# Anthropic: Use workspace-level key management
# Mistral: Monitor usage and rotate regularly
```

### 7. Secret Vault Integration (Advanced)
```bash
# Consider integrating HashiCorp Vault or similar for production
# Store secrets in vault instead of .env
# Fetch secrets at runtime
# Automatic rotation via vault policies
```

### 8. Documentation
```bash
# Maintain secret rotation log
cat > ~/.mascarade-secrets-backup/rotation_log.md << 'EOF'
# Secret Rotation Log

## 2026-03-16
- Rotated: MASCARADE_API_KEY, ANTHROPIC_API_KEY
- Reason: Quarterly rotation
- Verified: All services operational

## Template for future rotations:
## YYYY-MM-DD
## - Rotated: <list of secrets>
## - Reason: <scheduled/compromise/compliance>
## - Verified: <verification steps>
EOF
```

## Escalation

### When to Escalate
- Suspected key compromise with active abuse
- Unable to revoke compromised key at provider
- Multiple failed rotation attempts
- Data breach suspected alongside key leak
- Compliance violation requiring external audit

### Escalation Path
1. Immediately revoke compromised keys at provider
2. Document timeline of potential exposure
3. Review audit logs for unauthorized access
4. Notify affected users if personal data exposed
5. File incident report for compliance requirements
6. Consider external security audit if breach significant

## Related Documentation
- VM operations: `docs/RUNBOOK_VM_OPS.md`
- Security audit: `docs/SECURITY_AUDIT_VM_2026-03-03.md`
- Environment setup: `.env.example`
- Provider configuration: `core/mascarade/router/providers/`

## Post-Incident Review

After rotation (scheduled or emergency):
1. Document rotation date and secrets rotated
2. Verify all services functioning with new secrets
3. Confirm old secrets successfully revoked
4. Update rotation schedule for next cycle
5. Review any issues encountered during rotation
6. Update this runbook with lessons learned
7. If emergency rotation, conduct root cause analysis of leak
8. Implement additional safeguards to prevent future leaks

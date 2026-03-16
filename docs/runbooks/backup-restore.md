# Backup & Restore Runbook

Date: 2026-03-16

## Overview

This runbook covers backup and restoration procedures for the Mascarade orchestration system.
Critical data includes PostgreSQL database, agent configurations, execution history, trained
models, and system configuration. Regular backups protect against data loss from hardware
failure, corruption, or operational errors.

## Symptoms

### Scheduled Backup (Proactive)
- Daily/weekly backup schedule due
- Pre-upgrade backup required
- Disaster recovery testing
- Compliance requirement for data retention

### Emergency Restore (Reactive)
- Database corruption detected
- Accidental data deletion
- Failed migration requiring rollback
- Hardware failure requiring recovery
- Container volume lost or corrupted
- Ransomware or security incident

### Log Patterns (Indicating Data Issues)
```
ERROR: Database corruption detected
ERROR: Relation does not exist
ERROR: could not open file: No such file or directory
ERROR: unexpected end of file
WARNING: Invalid data in table
FATAL: database "mascarade" does not exist
```

## Diagnosis

### Step 1: Assess Data Loss Scope
```bash
cd /mascarade
# Check database accessibility
docker compose exec postgres psql -U mascarade -d mascarade -c "SELECT 1;"

# Check table existence
docker compose exec postgres psql -U mascarade -d mascarade -c "\dt"

# Check recent data
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Verify database size
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT pg_size_pretty(pg_database_size('mascarade'));"
```

### Step 2: Identify Available Backups
```bash
cd /mascarade
# List PostgreSQL backups
ls -lht backups/postgres/ | head -20

# Check backup sizes
du -sh backups/postgres/*

# Identify most recent valid backup
find backups/postgres/ -name "*.dump" -mtime -7 -ls
```

### Step 3: Verify Backup Integrity
```bash
cd /mascarade
# Test backup file integrity
LATEST_BACKUP=$(ls -t backups/postgres/*.dump | head -1)
file "$LATEST_BACKUP"

# Check if backup is complete (not truncated)
tail "$LATEST_BACKUP"

# Verify backup with pg_restore (dry run)
docker compose exec -T postgres pg_restore --list "$LATEST_BACKUP" > /dev/null
echo $?  # Should return 0
```

### Step 4: Check Backup Age
```bash
cd /mascarade
# Find last backup date
LATEST_BACKUP=$(ls -t backups/postgres/*.dump | head -1)
stat -f "Last backup: %Sm" "$LATEST_BACKUP"

# Check if backup is recent (< 24 hours)
BACKUP_AGE=$(( ($(date +%s) - $(stat -f %m "$LATEST_BACKUP")) / 3600 ))
echo "Backup age: $BACKUP_AGE hours"

if [ $BACKUP_AGE -gt 24 ]; then
  echo "WARNING: Backup is more than 24 hours old"
fi
```

### Step 5: Identify Data to Restore
```bash
# Full database restore needed if:
# - Complete database corruption
# - Major data loss across tables
# - Migration failure requiring full rollback

# Partial restore needed if:
# - Single table corrupted
# - Specific records accidentally deleted
# - Selective data recovery required
```

## Remediation

### Creating Backups

#### Manual PostgreSQL Backup
```bash
cd /mascarade
# Create immediate backup
scripts/pg_backup.sh

# Verify backup created
ls -lht backups/postgres/ | head -5

# Backup with custom name
BACKUP_FILE="backups/postgres/mascarade_pre_upgrade_$(date +%Y%m%d_%H%M%S).dump"
docker compose exec -T postgres pg_dump -U mascarade -Fc mascarade > "$BACKUP_FILE"
echo "Backup saved to: $BACKUP_FILE"
```

#### Backup with Verification
```bash
cd /mascarade
# Create and verify backup
scripts/pg_backup.sh

LATEST_BACKUP=$(ls -t backups/postgres/*.dump | head -1)
scripts/pg_restore_verify.sh --backup-file "$LATEST_BACKUP"

# Check verification result
if [ $? -eq 0 ]; then
  echo "Backup verified successfully"
else
  echo "ERROR: Backup verification failed"
fi
```

#### Backup Model Files (Ollama)
```bash
cd /mascarade
# Create models backup directory
mkdir -p backups/ollama

# Backup Ollama models
docker compose exec ollama tar czf /tmp/ollama_models_$(date +%Y%m%d).tar.gz /root/.ollama/models
docker compose cp ollama:/tmp/ollama_models_$(date +%Y%m%d).tar.gz backups/ollama/

# Verify backup
ls -lh backups/ollama/
```

#### Backup Configuration Files
```bash
cd /mascarade
# Create config backup directory
mkdir -p backups/config

# Backup .env (securely)
cp .env backups/config/.env.backup.$(date +%Y%m%d_%H%M%S)
chmod 600 backups/config/.env.backup.*

# Backup docker-compose and overrides
cp docker-compose.yml backups/config/docker-compose.yml.$(date +%Y%m%d)
[ -f docker-compose.override.yml ] && \
  cp docker-compose.override.yml backups/config/docker-compose.override.yml.$(date +%Y%m%d)

# Backup core config if customized
[ -d core/mascarade/config ] && \
  tar czf backups/config/core_config_$(date +%Y%m%d).tar.gz core/mascarade/config/
```

### Restoring from Backup

#### Pre-Restore Checklist
- [ ] Identify correct backup file to restore
- [ ] Verify backup integrity
- [ ] Stop services accessing database
- [ ] Create safety backup of current state (if possible)
- [ ] Document restore reason and timestamp
- [ ] Notify stakeholders of maintenance window

#### Full Database Restore
```bash
cd /mascarade
# Stop services using database
docker compose stop core api

# Identify backup to restore
BACKUP_FILE="backups/postgres/mascarade_20260316_120000.dump"
ls -lh "$BACKUP_FILE"

# Create safety backup of current state (if database is accessible)
docker compose exec -T postgres pg_dump -U mascarade -Fc mascarade > \
  backups/postgres/pre_restore_safety_$(date +%Y%m%d_%H%M%S).dump 2>/dev/null || \
  echo "Current database not accessible, skipping safety backup"

# Drop and recreate database
docker compose exec postgres psql -U mascarade -d postgres -c "DROP DATABASE IF EXISTS mascarade;"
docker compose exec postgres psql -U mascarade -d postgres -c "CREATE DATABASE mascarade OWNER mascarade;"

# Restore from backup
cat "$BACKUP_FILE" | docker compose exec -T postgres pg_restore -U mascarade -d mascarade --clean --if-exists

# Verify restoration
docker compose exec postgres psql -U mascarade -d mascarade -c "\dt"
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Restart services
docker compose start core api

# Test functionality
curl -fsS http://127.0.0.1:8100/health
```

#### Using Automated Restore Script
```bash
cd /mascarade
# Restore using helper script
scripts/pg_restore.sh --backup-file backups/postgres/mascarade_20260316_120000.dump

# Verify restoration
docker compose ps
curl -fsS http://127.0.0.1:8100/health
```

#### Partial Restore (Single Table)
```bash
cd /mascarade
BACKUP_FILE="backups/postgres/mascarade_20260316_120000.dump"
TABLE_NAME="agent_executions"

# Extract single table
docker compose exec -T postgres pg_restore -U mascarade -d mascarade \
  --table="$TABLE_NAME" --clean --if-exists < "$BACKUP_FILE"

# Verify table restored
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT count(*) FROM $TABLE_NAME;"
```

#### Restore Configuration Files
```bash
cd /mascarade
# Stop services
docker compose down

# Restore .env
BACKUP_ENV="backups/config/.env.backup.20260316_120000"
cp "$BACKUP_ENV" .env
chmod 600 .env

# Restore docker-compose.yml if needed
[ -f backups/config/docker-compose.yml.20260316 ] && \
  cp backups/config/docker-compose.yml.20260316 docker-compose.yml

# Restart with restored configuration
docker compose up -d
```

#### Restore Ollama Models
```bash
cd /mascarade
# Stop Ollama
docker compose stop ollama

# Restore models from backup
MODELS_BACKUP="backups/ollama/ollama_models_20260316.tar.gz"
docker compose cp "$MODELS_BACKUP" ollama:/tmp/ollama_models.tar.gz
docker compose exec ollama sh -c "cd / && tar xzf /tmp/ollama_models.tar.gz"

# Restart Ollama
docker compose start ollama

# Verify models restored
docker compose exec ollama ollama list
```

### Point-in-Time Recovery (PITR)
```bash
cd /mascarade
# If PostgreSQL WAL archiving is enabled, perform PITR

# Restore base backup
scripts/pg_restore.sh --backup-file backups/postgres/base_backup_20260316.dump

# Apply WAL archives up to target time
TARGET_TIME="2026-03-16 14:30:00"
docker compose exec postgres psql -U mascarade -d postgres -c \
  "SELECT pg_wal_replay_resume();"

# Verify recovery target reached
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT pg_last_wal_receive_lsn();"
```

### Recovery Verification

```bash
cd /mascarade
# Verify all services running
docker compose ps

# Check database health
docker compose exec postgres psql -U mascarade -d mascarade -c "\dt"
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT pg_size_pretty(pg_database_size('mascarade'));"

# Test API endpoints
curl -fsS http://127.0.0.1:8100/health | jq '.'
curl -fsS http://127.0.0.1:3100/health | jq '.'

# Verify agent functionality
curl -X POST http://127.0.0.1:3100/api/agents/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${MASCARADE_API_KEY}" \
  -d '{"agent": "general", "message": "test post-restore", "provider": "auto"}'

# Check logs for errors
docker compose logs --since 5m | grep -i error

# Verify data integrity
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT count(*) FROM agent_executions;"
```

## Prevention

### 1. Automated Backup Schedule
```bash
cd /mascarade
# Install automated backup cron jobs
scripts/install_backup_automation.sh

# Verify cron jobs installed
crontab -l | grep mascarade

# Default schedule:
# Daily backups at 2 AM
# Weekly retention cleanup
```

### 2. Backup Retention Policy
```bash
cd /mascarade
# Configure retention (keep 14 days)
scripts/pg_backup_retention.sh --days 14

# Add to cron for automatic cleanup
crontab -e
# 0 3 * * 0 /mascarade/scripts/pg_backup_retention.sh --days 14
```

### 3. Backup Verification Automation
```bash
cd /mascarade
# Create backup verification script
cat > scripts/verify_latest_backup.sh << 'EOF'
#!/bin/bash
cd /mascarade
LATEST_BACKUP=$(ls -t backups/postgres/*.dump | head -1)
scripts/pg_restore_verify.sh --backup-file "$LATEST_BACKUP"
if [ $? -eq 0 ]; then
  echo "$(date): Backup verification successful" >> logs/backup_verification.log
else
  echo "$(date): Backup verification FAILED" >> logs/backup_verification.log
  # Send alert
fi
EOF

chmod +x scripts/verify_latest_backup.sh

# Run verification weekly
crontab -e
# 0 4 * * 1 /mascarade/scripts/verify_latest_backup.sh
```

### 4. Off-Site Backup Replication
```bash
cd /mascarade
# Sync backups to remote location
cat > scripts/backup_sync.sh << 'EOF'
#!/bin/bash
# Sync to remote backup server
rsync -avz --delete \
  /mascarade/backups/ \
  backup-server:/backup/mascarade/

# Or use cloud storage
# aws s3 sync /mascarade/backups/ s3://my-backup-bucket/mascarade/
EOF

chmod +x scripts/backup_sync.sh

# Daily sync
crontab -e
# 0 5 * * * /mascarade/scripts/backup_sync.sh
```

### 5. Pre-Deployment Backups
```bash
cd /mascarade
# Create pre-deployment backup hook
cat > scripts/pre_deploy_backup.sh << 'EOF'
#!/bin/bash
echo "Creating pre-deployment backup..."
cd /mascarade
scripts/pg_backup.sh
LATEST=$(ls -t backups/postgres/*.dump | head -1)
echo "Backup created: $LATEST"
# Tag backup as pre-deployment
cp "$LATEST" "backups/postgres/pre_deploy_$(date +%Y%m%d_%H%M%S).dump"
EOF

chmod +x scripts/pre_deploy_backup.sh

# Include in deployment workflow
# ./scripts/pre_deploy_backup.sh && ./deploy/update.sh
```

### 6. Backup Monitoring & Alerting
```bash
cd /mascarade
# Monitor backup age and size
cat > scripts/backup_health_check.sh << 'EOF'
#!/bin/bash
LATEST_BACKUP=$(ls -t backups/postgres/*.dump | head -1)
BACKUP_AGE=$(( ($(date +%s) - $(stat -f %m "$LATEST_BACKUP")) / 3600 ))
BACKUP_SIZE=$(stat -f %z "$LATEST_BACKUP")

if [ $BACKUP_AGE -gt 48 ]; then
  echo "ALERT: Latest backup is $BACKUP_AGE hours old"
  # Send notification
fi

if [ $BACKUP_SIZE -lt 1000000 ]; then
  echo "ALERT: Latest backup is suspiciously small: $BACKUP_SIZE bytes"
  # Send notification
fi
EOF

chmod +x scripts/backup_health_check.sh

# Check daily
crontab -e
# 0 6 * * * /mascarade/scripts/backup_health_check.sh
```

### 7. Disaster Recovery Testing
```bash
cd /mascarade
# Quarterly DR drill
# 1. Create test restore environment
# 2. Restore from latest backup
# 3. Verify all functionality
# 4. Document recovery time
# 5. Update DR procedures

# Document in DR log
cat > backups/dr_test_log.md << 'EOF'
# Disaster Recovery Test Log

## 2026-03-16
- Backup tested: mascarade_20260316_020000.dump
- Restore time: 3 minutes
- Verification: All services operational
- Issues: None
- Action items: None

## Template for future tests:
## YYYY-MM-DD
## - Backup tested: <filename>
## - Restore time: <duration>
## - Verification: <results>
## - Issues: <any problems>
## - Action items: <improvements needed>
EOF
```

### 8. Backup Security
```bash
cd /mascarade
# Encrypt backups at rest
cat > scripts/pg_backup_encrypted.sh << 'EOF'
#!/bin/bash
BACKUP_FILE="backups/postgres/mascarade_$(date +%Y%m%d_%H%M%S).dump"
docker compose exec -T postgres pg_dump -U mascarade -Fc mascarade > "$BACKUP_FILE"

# Encrypt backup
gpg --symmetric --cipher-algo AES256 "$BACKUP_FILE"
shred -u "$BACKUP_FILE"  # Delete unencrypted version
echo "Encrypted backup: ${BACKUP_FILE}.gpg"
EOF

chmod +x scripts/pg_backup_encrypted.sh

# Ensure backups directory permissions
chmod 700 backups/
chmod 600 backups/postgres/*
```

## Escalation

### When to Escalate
- Backup restoration fails multiple times
- Data corruption extends to all backups
- Critical data unrecoverable
- Backup process consistently failing
- Disaster recovery exceeds RPO/RTO targets

### Escalation Path
1. Review all available backups for integrity
2. Attempt manual database recovery tools (pg_resetwal, etc.)
3. Contact PostgreSQL experts for recovery assistance
4. Consider data reconstruction from logs if available
5. Document data loss scope and impact
6. Implement additional backup redundancy to prevent recurrence

## Related Documentation
- Backup scripts: `scripts/pg_backup.sh`, `scripts/pg_restore.sh`
- VM operations: `docs/RUNBOOK_VM_OPS.md`
- Docker compose: `docker-compose.yml`
- Database migrations: `core/mascarade/migrations/`

## Post-Incident Review

After restore (scheduled test or emergency):
1. Document restore date, backup used, and reason
2. Measure actual RTO (Recovery Time Objective) achieved
3. Verify data loss (measure RPO - Recovery Point Objective)
4. Review backup/restore procedures for improvements
5. Update backup frequency if RPO not met
6. Document any gaps in backup coverage
7. Update this runbook with lessons learned
8. Consider additional backup strategies if single point of failure identified

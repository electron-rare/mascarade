# Database Connection Loss Runbook

Date: 2026-03-16

## Overview

This runbook covers PostgreSQL database connection failures in the Mascarade stack.
The system uses PostgreSQL for persistent storage of agent state, execution history,
and system configuration. Connection loss impacts all services relying on the database.

## Symptoms

### User-Facing
- API requests returning `503 Service Unavailable`
- Agent workflows failing to start or resume
- Unable to query execution history or logs
- Dashboard showing "Database Unavailable" errors
- Ops console unable to load metrics or traces

### System-Level
- Core service logs showing `Connection refused` or `Connection timeout`
- Health check endpoints failing for database-dependent services
- Docker container `mascarade-postgres` stopped or unhealthy
- Connection pool exhaustion errors
- Database migration failures on restart

### Log Patterns
```
ERROR: could not connect to server: Connection refused
ERROR: FATAL: remaining connection slots are reserved
ERROR: database "mascarade" does not exist
ERROR: connection to server was lost
WARNING: connection pool exhausted, waiting for available connection
```

## Diagnosis

### Step 1: Verify Database Container Status
```bash
cd /mascarade
docker compose ps postgres
# Look for: Up, healthy status

# If stopped or unhealthy:
docker compose logs postgres --tail 100
```

### Step 2: Test Database Connectivity
```bash
cd /mascarade
# Direct connection test
docker compose exec postgres psql -U mascarade -d mascarade -c "SELECT 1;"

# If connection fails, check network
docker compose exec core ping -c 3 postgres
```

### Step 3: Check Connection Pool Status
```bash
cd /mascarade
# View active connections
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Check connection limits
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SHOW max_connections;"

# View current connection count
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT count(*) FROM pg_stat_activity;"
```

### Step 4: Verify Database Credentials
```bash
cd /mascarade
# Check .env configuration
grep -E "POSTGRES_|DATABASE_URL" .env

# Verify credentials match between services
docker compose exec core env | grep DATABASE_URL
```

### Step 5: Check Disk Space and Resources
```bash
cd /mascarade
# Check disk usage
df -h

# Check PostgreSQL data directory
docker compose exec postgres df -h /var/lib/postgresql/data

# Check memory usage
docker stats --no-stream postgres
```

### Step 6: Review Database Logs
```bash
cd /mascarade
# Full PostgreSQL logs
docker compose logs postgres --since 30m

# Look for:
# - Crash/restart events
# - Corruption messages
# - Connection limit errors
# - Authentication failures
```

## Remediation

### Immediate Actions (First 5 Minutes)

#### 1. Restart PostgreSQL Container
```bash
cd /mascarade
docker compose restart postgres

# Wait for healthy status
docker compose ps postgres
# Verify health: Up (healthy)
```

#### 2. Verify Database Accessibility
```bash
cd /mascarade
# Test connection
docker compose exec postgres psql -U mascarade -d mascarade -c "SELECT NOW();"

# Check database exists
docker compose exec postgres psql -U mascarade -c "\l" | grep mascarade
```

#### 3. Restart Dependent Services
```bash
cd /mascarade
# Restart services that depend on database
docker compose restart core api

# Verify health
curl -fsS http://127.0.0.1:8100/health
curl -fsS http://127.0.0.1:3100/health
```

### Short-Term Actions (If Issue Persists)

#### 4. Check for Connection Leaks
```bash
cd /mascarade
# Identify long-running connections
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT pid, usename, application_name, state, query_start, query
   FROM pg_stat_activity
   WHERE state = 'idle in transaction'
   ORDER BY query_start;"

# Terminate idle connections (if necessary)
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'idle in transaction'
   AND query_start < NOW() - INTERVAL '10 minutes';"
```

#### 5. Increase Connection Pool Size
```bash
cd /mascarade
# Update PostgreSQL max_connections
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "ALTER SYSTEM SET max_connections = 200;"

# Restart to apply
docker compose restart postgres

# Update application pool size
echo "DATABASE_POOL_SIZE=20" >> .env
echo "DATABASE_MAX_OVERFLOW=10" >> .env
docker compose up -d core api
```

#### 6. Check for Database Corruption
```bash
cd /mascarade
# Run integrity checks
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT datname, pg_database_size(datname) FROM pg_database;"

# Check for corrupted indexes
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "REINDEX DATABASE mascarade;"
```

### Critical Recovery Actions

#### 7. Restore from Backup (If Database Corrupted)
```bash
cd /mascarade
# List available backups
ls -lh backups/postgres/

# Stop services using database
docker compose stop core api

# Restore from backup
scripts/pg_restore.sh --backup-file backups/postgres/mascarade_20260316_120000.dump

# Restart services
docker compose up -d core api
```

#### 8. Rebuild Database Container
```bash
cd /mascarade
# Backup current data first
scripts/pg_backup.sh

# Stop and remove container
docker compose down postgres
docker volume ls | grep mascarade-postgres

# Recreate with fresh volume (DESTRUCTIVE - only if restore available)
docker volume rm mascarade-postgres-data
docker compose up -d postgres

# Restore data
scripts/pg_restore.sh --backup-file backups/postgres/latest.dump
```

### Recovery Verification

```bash
cd /mascarade
# Verify database health
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT version();"

# Verify tables exist
docker compose exec postgres psql -U mascarade -d mascarade -c "\dt"

# Test application connectivity
curl -fsS http://127.0.0.1:8100/health | jq '.database'

# Verify data integrity
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Check recent logs for errors
docker compose logs postgres --since 5m | grep -i error
```

## Prevention

### 1. Automated Backups
Ensure regular backups are configured:
```bash
cd /mascarade
# Install backup automation
scripts/install_backup_automation.sh

# Verify cron job
crontab -l | grep pg_backup

# Manual backup test
scripts/pg_backup.sh
ls -lh backups/postgres/
```

### 2. Connection Pool Configuration
Optimize connection pooling:
```bash
cd /mascarade
# In .env
echo "DATABASE_POOL_SIZE=20" >> .env
echo "DATABASE_MAX_OVERFLOW=10" >> .env
echo "DATABASE_POOL_TIMEOUT=30" >> .env
echo "DATABASE_POOL_RECYCLE=3600" >> .env

# Apply changes
docker compose up -d core api
```

### 3. Database Monitoring
Set up monitoring for connection health:
```bash
cd /mascarade
# Enable ops-console monitoring
./setup --with core,api,ops-console,prometheus,grafana --yes

# Access Grafana at http://127.0.0.1:3100/grafana
# Configure PostgreSQL dashboard
# Set alerts for:
# - Connection pool > 80% utilization
# - Database down > 1 minute
# - Disk usage > 85%
```

### 4. Resource Limits
Configure appropriate resource limits:
```yaml
# In docker-compose.yml
services:
  postgres:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2'
        reservations:
          memory: 512M
```

### 5. Regular Health Checks
Implement proactive health checks:
```bash
cd /mascarade
# Create health check script
cat > scripts/db_health_check.sh << 'EOF'
#!/bin/bash
docker compose exec -T postgres psql -U mascarade -d mascarade -c "SELECT 1;" > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "Database health check failed at $(date)"
  # Trigger alert or auto-restart
fi
EOF

chmod +x scripts/db_health_check.sh

# Add to cron
crontab -e
# */5 * * * * /mascarade/scripts/db_health_check.sh
```

### 6. Backup Verification
Regularly test backup restoration:
```bash
cd /mascarade
# Test restore process monthly
scripts/pg_restore_verify.sh --backup-file backups/postgres/latest.dump

# Verify integrity
echo "Backup verification: $(date)" >> logs/backup_verification.log
```

### 7. Connection Leak Detection
Monitor for connection leaks in application code:
```bash
cd /mascarade
# Review connection patterns weekly
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT application_name, count(*), state
   FROM pg_stat_activity
   GROUP BY application_name, state
   ORDER BY count(*) DESC;"
```

### 8. Database Maintenance
Schedule regular maintenance:
```bash
cd /mascarade
# Create maintenance script
cat > scripts/db_maintenance.sh << 'EOF'
#!/bin/bash
# Run VACUUM and ANALYZE weekly
docker compose exec -T postgres psql -U mascarade -d mascarade -c "VACUUM ANALYZE;"
# Reindex monthly
docker compose exec -T postgres psql -U mascarade -d mascarade -c "REINDEX DATABASE mascarade;"
EOF

chmod +x scripts/db_maintenance.sh
```

## Escalation

### When to Escalate
- Database unrecoverable from backups
- Data corruption affecting critical tables
- Persistent connection failures after all remediation steps
- Disk space exhaustion with no recovery path

### Escalation Path
1. Review PostgreSQL logs for critical errors
2. Check backup integrity and availability
3. Document exact failure symptoms and timeline
4. Consider migrating to new database instance
5. Review incident for architectural improvements

## Related Documentation
- Backup scripts: `scripts/pg_backup.sh`, `scripts/pg_restore.sh`
- VM operations: `docs/RUNBOOK_VM_OPS.md`
- Docker compose config: `docker-compose.yml`
- Database migrations: `core/mascarade/migrations/`

## Post-Incident Review

After resolution:
1. Document root cause (connection leak, corruption, resource exhaustion, etc.)
2. Review backup/restore procedures effectiveness
3. Update connection pool sizing based on actual usage patterns
4. Implement additional monitoring if blind spots identified
5. Consider database replication for high availability if needed
6. Update this runbook with lessons learned

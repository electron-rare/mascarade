# High Memory/CPU Usage Runbook

Date: 2026-03-16

## Overview

This runbook covers diagnosing and resolving high memory and CPU usage in the Mascarade stack.
The system runs multiple containerized services (core, api, ollama, postgres, etc.) that can
experience resource exhaustion due to heavy workloads, memory leaks, or misconfigurations.

## Symptoms

### User-Facing
- Slow API response times or timeouts
- Agent requests taking significantly longer than normal
- System unresponsive or laggy
- Container restarts or OOM (Out of Memory) kills
- Docker daemon becoming unresponsive

### System-Level
- Host memory usage > 90%
- CPU usage sustained > 80% across cores
- Docker containers being killed by OOM
- Swap usage increasing significantly
- System load average > number of CPU cores
- Disk I/O wait times elevated

### Log Patterns
```
ERROR: Container killed by OOM killer
WARNING: Memory usage at 95%
ERROR: Process killed: signal 9 (SIGKILL)
ERROR: fork failed: Cannot allocate memory
WARNING: High CPU usage detected: 98%
```

## Diagnosis

### Step 1: Identify Resource Usage by Container
```bash
cd /mascarade
# Real-time container stats
docker stats --no-stream

# Continuous monitoring
docker stats

# Sort by memory usage
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | sort -k3 -h

# Sort by CPU usage
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | sort -k2 -h
```

### Step 2: Check Host System Resources
```bash
# Overall system stats
top -b -n 1 | head -20

# Memory breakdown
free -h

# CPU per core
mpstat -P ALL 1 5

# Disk I/O
iostat -x 2 5

# Load average
uptime

# Check for swap usage
swapon --show
vmstat 1 5
```

### Step 3: Identify Heavy Processes
```bash
# Top memory consumers
ps aux --sort=-%mem | head -20

# Top CPU consumers
ps aux --sort=-%cpu | head -20

# Docker-specific processes
ps aux | grep docker | head -20
```

### Step 4: Check for Memory Leaks
```bash
cd /mascarade
# Monitor container memory over time
for i in {1..10}; do
  docker stats --no-stream --format "{{.Name}}\t{{.MemUsage}}" | grep -E "core|api|ollama"
  sleep 5
done

# Check container logs for OOM events
docker compose logs --tail 500 | grep -i "out of memory\|oom\|killed"
```

### Step 5: Review Container Resource Limits
```bash
cd /mascarade
# Inspect container limits
docker inspect mascarade-core | jq '.[].HostConfig.Memory'
docker inspect mascarade-api | jq '.[].HostConfig.Memory'
docker inspect mascarade-ollama | jq '.[].HostConfig.Memory'

# Check compose configuration
grep -A5 "resources:" docker-compose.yml
```

### Step 6: Analyze Specific Services

#### Core Service
```bash
cd /mascarade
# Check for pending agent tasks
docker compose exec core ps aux

# Review recent activity
docker compose logs core --tail 200 | grep -i "request\|agent"
```

#### Ollama Service (GPU/Model Loading)
```bash
cd /mascarade
# Check loaded models
docker compose exec ollama ollama list

# GPU memory usage (if NVIDIA GPU)
nvidia-smi

# Check model size
docker compose exec ollama du -sh /root/.ollama/models/*
```

#### PostgreSQL
```bash
cd /mascarade
# Check active queries
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT pid, query_start, state, query
   FROM pg_stat_activity
   WHERE state != 'idle'
   ORDER BY query_start;"

# Check database size
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "SELECT pg_size_pretty(pg_database_size('mascarade'));"
```

## Remediation

### Immediate Actions (First 5 Minutes)

#### 1. Identify and Stop Resource-Heavy Container
```bash
cd /mascarade
# Identify culprit
docker stats --no-stream

# Restart heavy container
docker compose restart <service-name>

# If unresponsive, force stop
docker compose stop <service-name>
docker compose start <service-name>
```

#### 2. Free Up Memory (Emergency)
```bash
# Clear system caches (safe operation)
sudo sync && sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'

# Stop non-critical services temporarily
cd /mascarade
docker compose stop generate-audio  # If running
docker compose stop promtail        # If running
docker compose stop grafana         # If running
```

#### 3. Check for Runaway Processes
```bash
# Kill specific heavy process if identified
docker compose exec <service> ps aux
docker compose exec <service> kill -9 <pid>

# Or restart entire service
docker compose restart <service>
```

### Short-Term Actions (Next 30 Minutes)

#### 4. Configure Resource Limits
```bash
cd /mascarade
# Edit docker-compose.yml to add/update limits
cat >> docker-compose.override.yml << 'EOF'
services:
  core:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
        reservations:
          memory: 1G

  api:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1'
        reservations:
          memory: 512M

  ollama:
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4'
        reservations:
          memory: 2G

  postgres:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2'
        reservations:
          memory: 512M
EOF

# Apply changes
docker compose up -d
```

#### 5. Optimize Ollama Model Loading
```bash
cd /mascarade
# Unload unused models
docker compose exec ollama ollama list

# Stop ollama temporarily and clear cache
docker compose stop ollama
docker compose exec ollama rm -rf /root/.ollama/models/.cache
docker compose start ollama

# Pre-load only required models
docker compose exec ollama ollama pull qwen2.5:14b
```

#### 6. Reduce Concurrent Workloads
```bash
cd /mascarade
# Limit concurrent agent requests in core
echo "MAX_CONCURRENT_AGENTS=3" >> .env
echo "WORKER_CONCURRENCY=2" >> .env

# Restart to apply
docker compose up -d core
```

#### 7. Clean Up Docker Resources
```bash
# Remove stopped containers
docker container prune -f

# Remove unused images
docker image prune -a -f

# Remove unused volumes
docker volume prune -f

# Remove unused networks
docker network prune -f

# Full cleanup
docker system prune -a --volumes -f
```

#### 8. Optimize PostgreSQL
```bash
cd /mascarade
# Reduce PostgreSQL memory usage
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "ALTER SYSTEM SET shared_buffers = '256MB';"
docker compose exec postgres psql -U mascarade -d mascarade -c \
  "ALTER SYSTEM SET work_mem = '4MB';"

# Restart postgres
docker compose restart postgres

# Vacuum database
docker compose exec postgres psql -U mascarade -d mascarade -c "VACUUM FULL ANALYZE;"
```

### Long-Term Fixes

#### 9. Implement Request Throttling
```bash
cd /mascarade
# Add rate limiting to prevent resource exhaustion
echo "ROUTER_RATE_LIMIT_PER_MINUTE=30" >> .env
echo "API_RATE_LIMIT_PER_IP=60" >> .env

docker compose up -d core api
```

#### 10. Set Up Resource Monitoring
```bash
cd /mascarade
# Enable full observability stack
./setup --with core,api,ops-console,prometheus,grafana --yes

# Access Grafana at http://127.0.0.1:3100/grafana
# Configure alerts for:
# - Memory usage > 80%
# - CPU usage > 80% for > 5 minutes
# - Swap usage > 50%
```

### Recovery Verification

```bash
cd /mascarade
# Check all services are healthy
docker compose ps

# Verify resource usage is normal
docker stats --no-stream

# Test API responsiveness
time curl -fsS http://127.0.0.1:8100/health
time curl -fsS http://127.0.0.1:3100/health

# Check system load
uptime

# Verify memory availability
free -h
```

## Prevention

### 1. Set Resource Limits
Always define resource limits in docker-compose.yml:
```yaml
services:
  core:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
```

### 2. Implement Monitoring & Alerting
```bash
cd /mascarade
# Deploy monitoring stack
./setup --with core,api,ops-console,prometheus,grafana,loki --yes

# Configure alerts for:
# - Container memory > 80%
# - Host memory > 85%
# - CPU sustained > 80%
# - OOM kills detected
```

### 3. Regular Cleanup Automation
```bash
cd /mascarade
# Create cleanup script
cat > scripts/resource_cleanup.sh << 'EOF'
#!/bin/bash
# Clean up Docker resources weekly
docker system prune -f
docker volume prune -f
docker image prune -a -f --filter "until=168h"
EOF

chmod +x scripts/resource_cleanup.sh

# Add to cron
crontab -e
# 0 3 * * 0 /mascarade/scripts/resource_cleanup.sh
```

### 4. Optimize Model Loading
```bash
cd /mascarade
# Only keep essential models loaded
docker compose exec ollama ollama list

# Configure model retention policy
echo "OLLAMA_KEEP_ALIVE=5m" >> .env
docker compose up -d ollama
```

### 5. Database Maintenance
```bash
cd /mascarade
# Regular VACUUM to prevent bloat
cat > scripts/db_vacuum.sh << 'EOF'
#!/bin/bash
docker compose exec -T postgres psql -U mascarade -d mascarade -c "VACUUM ANALYZE;"
EOF

chmod +x scripts/db_vacuum.sh

# Weekly vacuum
crontab -e
# 0 2 * * 0 /mascarade/scripts/db_vacuum.sh
```

### 6. Implement Circuit Breakers
Configure application to fail fast under high load:
```bash
cd /mascarade
# Set sensible timeouts
echo "AGENT_TIMEOUT_SECONDS=60" >> .env
echo "ROUTER_TIMEOUT_SECONDS=30" >> .env
echo "DATABASE_TIMEOUT_SECONDS=10" >> .env

docker compose up -d
```

### 7. Capacity Planning
Monitor trends and plan upgrades:
```bash
# Review weekly resource trends in Grafana
# Document peak usage times
# Plan horizontal scaling if needed
# Consider dedicated GPU server for Ollama
```

### 8. Log Rotation
Prevent disk exhaustion from logs:
```bash
cd /mascarade
# Configure log rotation in docker-compose.yml
cat >> docker-compose.override.yml << 'EOF'
x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"

services:
  core:
    logging: *default-logging
  api:
    logging: *default-logging
  ollama:
    logging: *default-logging
  postgres:
    logging: *default-logging
EOF

docker compose up -d
```

## Escalation

### When to Escalate
- Host system completely unresponsive
- Repeated OOM kills despite resource limits
- Persistent high CPU with no identifiable cause
- Memory leaks in application code suspected
- Hardware limitations reached

### Escalation Path
1. Document resource usage patterns over time
2. Review application code for memory leaks
3. Consider horizontal scaling (multiple instances)
4. Evaluate hardware upgrade requirements
5. Implement service mesh for better resource distribution

## Related Documentation
- VM operations: `docs/RUNBOOK_VM_OPS.md`
- Docker compose: `docker-compose.yml`
- Monitoring architecture: `docs/OBSERVABILITY_ARCHITECTURE.md`
- GPU benchmarking: `docs/FINETUNING_4090_PARALLEL_PLAN.md`

## Post-Incident Review

After resolution:
1. Document which service(s) caused high resource usage
2. Identify root cause (workload spike, memory leak, misconfiguration)
3. Review and update resource limits based on actual requirements
4. Implement additional monitoring if gaps identified
5. Update capacity planning based on usage trends
6. Consider architectural changes if resource issues are systemic
7. Update this runbook with new patterns observed

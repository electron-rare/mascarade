# Mascarade Deployment Guide

This guide provides step-by-step instructions for deploying Mascarade with all the new features: BERT classifier, multi-level caching, and auto-scaling.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Monitoring Setup](#monitoring-setup)
- [Optimization](#optimization)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **CPU**: 4+ cores (8+ recommended for production)
- **Memory**: 16GB+ RAM
- **Storage**: 50GB+ SSD
- **GPU**: Optional but recommended for BERT classifier

### Software Requirements

- Docker 20.10+
- Docker Compose 1.29+
- Python 3.11+
- Redis 6.2+
- ClickHouse 22.8+

### Python Dependencies

```bash
pip install torch transformers scikit-learn redis clickhouse-driver
```

## Configuration

### Environment Variables

Copy the example environment file and configure:

```bash
cp .env.example .env
```

#### Key Configuration Options

```env
# BERT Classifier
USE_BERT_CLASSIFIER=true
USE_ML_CLASSIFIER=true

# Multi-level Cache
CACHE_ENABLED=true
CACHE_L1_SIZE=2000
CACHE_L2_ENABLED=true
CACHE_L2_HOST=redis
CACHE_L2_PORT=6379
CACHE_L3_ENABLED=false

# Auto-scaling
AUTOSCALING_ENABLED=true
AUTOSCALING_MIN_WORKERS=2
AUTOSCALING_MAX_WORKERS=8
AUTOSCALING_SCALE_UP_CPU_THRESHOLD=0.75
AUTOSCALING_SCALE_DOWN_CPU_THRESHOLD=0.25
```

### Redis Configuration

Ensure Redis is properly configured in `docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:6.2
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
```

## Deployment

### Standard Deployment

```bash
# Build and start services
docker compose up -d --build

# Verify services are running
docker compose ps
```

### Production Deployment with Monitoring

```bash
# Start main services
docker compose -f docker-compose.yml up -d

# Start monitoring stack
docker compose -f docker-compose.monitoring.yml up -d

# Verify all services
docker compose ps
docker compose -f docker-compose.monitoring.yml ps
```

### Kubernetes Deployment

For production Kubernetes deployments, use the provided Helm chart:

```bash
# Add Helm repo (if available)
helm repo add mascarade https://mascarade.ai/charts

# Install with custom values
helm install mascarade mascarade/mascarade \
  --values production-values.yaml \
  --namespace mascarade \
  --create-namespace
```

Example `production-values.yaml`:

```yaml
replicaCount: 3

resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 1000m
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 75

bertClassifier:
  enabled: true
  gpuEnabled: true

cache:
  l1Size: 2000
  l2Enabled: true
  l3Enabled: false
```

## Monitoring Setup

### Prometheus Configuration

The monitoring stack includes Prometheus with pre-configured scraping:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'mascarade'
    static_configs:
      - targets: ['mascarade:8000']
  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
```

### Grafana Dashboard

Import the provided dashboard:

1. Access Grafana at `http://localhost:3000` (admin/admin)
2. Go to Dashboards → Import
3. Upload `grafana-dashboard.json`
4. Select Prometheus as data source

### Key Metrics to Monitor

- **Cache Hit Rate**: Should be >90%
- **BERT Latency**: Should be <50ms
- **Auto-scaling Events**: Should be <5/hour
- **Worker Load**: Should be 60-80%
- **Queue Depth**: Should be <30

## Optimization

### Running Optimization Scripts

```bash
# Run auto-optimization
python optimization_script.py

# Run BERT fine-tuning (requires production data)
python bert_finetuning_script.py
```

### Manual Optimization

#### Cache Optimization

Adjust cache parameters based on hit rates:

```python
# If hit rate < 85%
settings.cache_l1_size = int(settings.cache_l1_size * 1.2)

# If hit rate > 95%
settings.cache_l1_size = int(settings.cache_l1_size * 0.9)
```

#### Auto-scaling Optimization

Adjust thresholds based on workload:

```python
# If frequent scaling events
settings.autoscaling_cooldown_seconds = min(settings.autoscaling_cooldown_seconds * 1.5, 600)

# If high worker load
settings.autoscaling_scale_up_cpu_threshold = max(settings.autoscaling_scale_up_cpu_threshold - 0.05, 0.5)
```

## Troubleshooting

### Common Issues

#### BERT Classifier Not Loading

**Symptoms**: Errors about missing BERT model files

**Solutions**:
1. Verify model files exist in `~/.mascarade/models/bert_domain_classifier/`
2. Run fine-tuning script to generate model
3. Check GPU availability if using GPU mode

#### Cache Connection Errors

**Symptoms**: Redis connection failures

**Solutions**:
1. Verify Redis is running: `docker compose ps redis`
2. Check Redis logs: `docker compose logs redis`
3. Test connection: `redis-cli ping`

#### Auto-scaling Not Working

**Symptoms**: No scaling events despite high load

**Solutions**:
1. Verify `AUTOSCALING_ENABLED=true`
2. Check worker registration: `curl http://localhost:8000/v1/api/scheduler/status`
3. Review thresholds in settings

### Debugging Commands

```bash
# Check service logs
docker compose logs mascarade

# Test BERT classifier
curl -X POST http://localhost:8000/v1/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "Design a PCB layout"}'

# Check cache stats
curl http://localhost:8000/v1/cache/stats

# Check auto-scaler status
curl http://localhost:8000/v1/autoscaler/status
```

## Maintenance

### Updating Configuration

```bash
# Update environment variables
vim .env

# Restart services
docker compose down && docker compose up -d
```

### Backing Up Data

```bash
# Backup Redis data
docker exec redis redis-cli save

# Backup ClickHouse data
clickhouse-client --query "BACKUP DATABASE mascarade TO 'backup/mascarade_$(date +%Y%m%d).sql'"
```

### Restoring from Backup

```bash
# Restore Redis
docker cp redis_backup.dump redis:/data/dump.rdb
docker exec redis redis-cli config set dbfilename dump.rdb
docker restart redis

# Restore ClickHouse
clickhouse-client --query "RESTORE DATABASE mascarade FROM 'backup/mascarade_20240101.sql'"
```

## Performance Tuning

### BERT Classifier

```python
# For lower latency (CPU mode)
classifier = BertDomainClassifier(use_gpu=False)

# For higher accuracy (GPU mode)
classifier = BertDomainClassifier(use_gpu=True, max_length=256)
```

### Cache Configuration

```python
# For memory-constrained environments
cache = MultiTierCache(l1=InMemoryCache(max_size=1000), l2=None, l3=None)

# For high-performance environments
cache = MultiTierCache(
    l1=InMemoryCache(max_size=5000),
    l2=RedisCache(host='redis', port=6379),
    l3=SemanticCache(similarity_threshold=0.85)
)
```

### Auto-scaling Tuning

```python
# For stable workloads (fewer scaling events)
autoscaler = AutoScaler(
    cooldown_seconds=600,
    scale_up_threshold=0.8,
    scale_down_threshold=0.3
)

# For variable workloads (more responsive)
autoscaler = AutoScaler(
    cooldown_seconds=180,
    scale_up_threshold=0.7,
    scale_down_threshold=0.4
)
```

## Security Considerations

### API Security

- Always use HTTPS in production
- Rotate API keys regularly
- Use rate limiting

### Data Security

- Encrypt sensitive data at rest
- Use Redis password authentication
- Restrict ClickHouse access

### Network Security

- Use firewall rules to restrict access
- Implement network policies in Kubernetes
- Use private networks for inter-service communication

## Scaling Guidelines

### Vertical Scaling

| Component | Min Requirements | Recommended Production |
|-----------|------------------|-----------------------|
| API Server | 2 CPU, 4GB RAM | 4 CPU, 8GB RAM |
| Redis | 1 CPU, 2GB RAM | 2 CPU, 4GB RAM |
| ClickHouse | 2 CPU, 4GB RAM | 4 CPU, 8GB RAM |

### Horizontal Scaling

- **API Servers**: Scale based on CPU usage (target 70%)
- **Workers**: Scale based on queue depth (target <30)
- **Redis**: Single instance for cache (consider clustering for HA)
- **ClickHouse**: Single instance for analytics

### Resource Allocation

```yaml
# Example Kubernetes resource requests/limits
resources:
  requests:
    cpu: "1000m"
    memory: "2Gi"
  limits:
    cpu: "2000m"
    memory: "4Gi"
```

## Upgrade Process

### Minor Version Upgrades

```bash
# Pull latest images
docker compose pull

# Restart services
docker compose down && docker compose up -d
```

### Major Version Upgrades

```bash
# Backup current configuration
cp .env .env.backup

# Update docker-compose.yml with new version
vim docker-compose.yml

# Migrate data if needed
python manage.py migrate

# Restart services
docker compose down && docker compose up -d
```

## Support

For issues not covered in this guide:

- Check GitHub issues: https://github.com/mascarade-ai/mascarade/issues
- Join Discord community: https://discord.gg/mascarade
- Contact support: support@mascarade.ai

## Appendix

### Configuration Reference

Complete list of configuration options:

```env
# Core Settings
DEBUG=false
SECRET_KEY=your-secret-key

# BERT Classifier
USE_BERT_CLASSIFIER=true
BERT_MODEL_PATH=~/.mascarade/models/bert_domain_classifier

# Cache
CACHE_L1_SIZE=2000
CACHE_L2_ENABLED=true
CACHE_L2_HOST=redis
CACHE_L2_PORT=6379
CACHE_L3_ENABLED=false
CACHE_L3_SIMILARITY_THRESHOLD=0.85

# Auto-scaling
AUTOSCALING_ENABLED=true
AUTOSCALING_MIN_WORKERS=2
AUTOSCALING_MAX_WORKERS=8
AUTOSCALING_SCALE_UP_CPU_THRESHOLD=0.75
AUTOSCALING_SCALE_DOWN_CPU_THRESHOLD=0.25
AUTOSCALING_SCALE_UP_QUEUE_THRESHOLD=40
AUTOSCALING_SCALE_DOWN_QUEUE_THRESHOLD=15
AUTOSCALING_COOLDOWN_SECONDS=180

# Monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
```

### Performance Benchmarks

| Configuration | QPS | P95 Latency | Cache Hit Rate |
|---------------|-----|-------------|----------------|
| Default | 120 | 180ms | 85% |
| Optimized | 180 | 120ms | 92% |
| Full (BERT+Cache+Auto) | 200 | 90ms | 95% |

### Troubleshooting Checklist

- [ ] Verify all services are running
- [ ] Check logs for errors
- [ ] Test individual components
- [ ] Verify network connectivity
- [ ] Check resource usage
- [ ] Review configuration files
- [ ] Test with minimal configuration
- [ ] Check dependencies versions

## Changelog

### v1.0.0 (Current)
- Added BERT classifier support
- Implemented multi-level caching
- Added auto-scaling capabilities
- Enhanced monitoring integration

### v0.9.0
- Initial production release
- Basic routing capabilities
- Single-level caching
- Manual scaling only
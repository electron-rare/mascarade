# Metrics Tracking System

## Overview
Comprehensive metrics tracking for LLM providers to monitor performance, cost, and usage patterns.

## Core Metrics Structure

### File: `core/mascarade/metrics/tracker.py`
```python
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime
import time

@dataclass
class ProviderMetrics:
    """Performance metrics for a single provider"""
    provider_name: str
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    last_used: datetime = None
    
    def update(
        self,
        tokens: int,
        cost: float,
        response_time: float,
        success: bool
    ):
        """Update metrics with new request data"""
        self.total_requests += 1
        self.total_tokens += tokens
        self.total_cost += cost
        
        # Update average response time
        if self.total_requests == 1:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (
                (self.avg_response_time * (self.total_requests - 1)) + response_time
            ) / self.total_requests
        
        # Update error rate
        if not success:
            self.error_rate = (
                (self.error_rate * (self.total_requests - 1)) + 1
            ) / self.total_requests
        
        self.last_used = datetime.now()

class MetricsTracker:
    """Central metrics tracking system"""
    
    def __init__(self):
        self.providers: Dict[str, ProviderMetrics] = {}
        self.request_history: List[Dict] = []
        self.max_history = 1000
    
    def track_request(
        self,
        provider_name: str,
        tokens: int,
        cost: float,
        response_time: float,
        success: bool,
        strategy: str = None
    ):
        """Track a completed request"""
        if provider_name not in self.providers:
            self.providers[provider_name] = ProviderMetrics(provider_name)
        
        self.providers[provider_name].update(tokens, cost, response_time, success)
        
        # Store in history
        request_data = {
            "timestamp": datetime.now(),
            "provider": provider_name,
            "tokens": tokens,
            "cost": cost,
            "response_time": response_time,
            "success": success,
            "strategy": strategy
        }
        
        self.request_history.append(request_data)
        if len(self.request_history) > self.max_history:
            self.request_history.pop(0)
    
    def get_provider_stats(self, provider_name: str) -> Dict:
        """Get statistics for a specific provider"""
        if provider_name not in self.providers:
            return {}
        
        metrics = self.providers[provider_name]
        return {
            "total_requests": metrics.total_requests,
            "total_tokens": metrics.total_tokens,
            "total_cost": round(metrics.total_cost, 4),
            "avg_response_time": round(metrics.avg_response_time, 2),
            "error_rate": round(metrics.error_rate * 100, 2),
            "last_used": metrics.last_used.isoformat() if metrics.last_used else None
        }
    
    def get_summary(self) -> Dict:
        """Get overall system metrics"""
        return {
            "providers": {name: self.get_provider_stats(name) 
                         for name in self.providers},
            "total_requests": sum(p.total_requests for p in self.providers.values()),
            "total_cost": round(sum(p.total_cost for p in self.providers.values()), 4),
            "best_performer": self._get_best_performer()
        }
    
    def _get_best_performer(self) -> str:
        """Determine best performing provider"""
        if not self.providers:
            return None
        
        # Score based on response time and error rate
        best_provider = None
        best_score = float('inf')
        
        for name, metrics in self.providers.items():
            if metrics.total_requests < 5:  # Need minimum data
                continue
            
            score = (
                metrics.avg_response_time * 
                (1 + metrics.error_rate * 10)  # Penalize errors
            )
            
            if score < best_score:
                best_score = score
                best_provider = name
        
        return best_provider
```

## Router Integration

### Enhanced Router with Metrics
```python
# core/mascarade/router/router.py
from ..metrics.tracker import MetricsTracker

class Router:
    def __init__(self):
        self._providers = {}
        self.metrics = MetricsTracker()
        self._register_defaults()
    
    async def send(self, messages: list[dict], **kwargs) -> LLMResponse:
        start_time = time.time()
        strategy = kwargs.get('strategy', Strategy.BEST)
        
        try:
            selected = self._select_provider(strategy, kwargs.get('provider'))
            response = await selected.send(messages, **kwargs)
            
            # Calculate metrics
            response_time = time.time() - start_time
            token_count = sum(response.usage.values())
            cost = self._calculate_cost(selected, token_count)
            
            # Track successful request
            self.metrics.track_request(
                provider_name=selected.name,
                tokens=token_count,
                cost=cost,
                response_time=response_time,
                success=True,
                strategy=strategy.value
            )
            
            return response
            
        except Exception as e:
            response_time = time.time() - start_time
            
            # Track failed request
            if 'provider' in kwargs and kwargs['provider'] in self._providers:
                self.metrics.track_request(
                    provider_name=kwargs['provider'],
                    tokens=0,
                    cost=0,
                    response_time=response_time,
                    success=False,
                    strategy=strategy.value
                )
            
            raise
    
    def _calculate_cost(self, provider: LLMProvider, tokens: int) -> float:
        """Calculate cost based on provider pricing"""
        input_tokens = tokens  # Simplified - would need to split input/output
        output_tokens = 0
        
        # Cost per 1M tokens
        input_cost, output_cost = provider.cost_per_million
        
        return (input_tokens * input_cost / 1_000_000) + \
               (output_tokens * output_cost / 1_000_000)
```

## API Endpoints for Metrics

### File: `api/src/routes/metrics.ts`
```typescript
import { Hono } from 'hono'
import { z } from 'zod'
import { zValidator } from '@hono/zod-validator'

const app = new Hono()

// Get all metrics
app.get('/metrics', async (c) => {
  try {
    const metrics = await coreClient.getMetrics()
    return c.json(metrics)
  } catch (error) {
    return c.json({ error: 'Failed to fetch metrics' }, 500)
  }
})

// Get provider-specific metrics
const providerSchema = z.object({
  provider: z.enum(['claude', 'openai', 'mistral'])
})

app.get('/metrics/:provider', zValidator('param', providerSchema), async (c) => {
  const { provider } = c.req.valid('param')
  
  try {
    const stats = await coreClient.getProviderStats(provider)
    return c.json(stats)
  } catch (error) {
    return c.json({ error: `Failed to fetch ${provider} metrics` }, 500)
  }
})

// Reset metrics (admin only)
app.post('/metrics/reset', async (c) => {
  try {
    await coreClient.resetMetrics()
    return c.json({ success: true })
  } catch (error) {
    return c.json({ error: 'Failed to reset metrics' }, 500)
  }
})

export default app
```

## Dashboard Visualization

### Metrics Dashboard Component
```typescript
// components/MetricsDashboard.tsx
import { useEffect, useState } from 'react'
import { BarChart, PieChart, LineChart } from 'react-chartjs-2'

interface ProviderStats {
  total_requests: number
  total_tokens: number
  total_cost: number
  avg_response_time: number
  error_rate: number
}

export function MetricsDashboard() {
  const [metrics, setMetrics] = useState<any>(null)
  const [timeRange, setTimeRange] = useState('24h')
  
  useEffect(() => {
    const fetchMetrics = async () => {
      const response = await fetch('/api/metrics')
      const data = await response.json()
      setMetrics(data)
    }
    
    fetchMetrics()
    const interval = setInterval(fetchMetrics, 30000)  // Refresh every 30s
    
    return () => clearInterval(interval)
  }, [timeRange])
  
  if (!metrics) return <div>Loading metrics...</div>
  
  const chartData = {
    labels: Object.keys(metrics.providers),
    datasets: [
      {
        label: 'Requests',
        data: Object.values(metrics.providers).map(p => p.total_requests),
        backgroundColor: 'rgba(75, 192, 192, 0.6)'
      }
    ]
  }
  
  return (
    <div className="metrics-dashboard">
      <h2>LLM Provider Metrics</h2>
      
      <div className="summary-cards">
        <div className="card">
          <h3>Total Requests</h3>
          <p>{metrics.total_requests}</p>
        </div>
        <div className="card">
          <h3>Total Cost</h3>
          <p>${metrics.total_cost.toFixed(4)}</p>
        </div>
        <div className="card">
          <h3>Best Performer</h3>
          <p>{metrics.best_performer || 'N/A'}</p>
        </div>
      </div>
      
      <div className="charts">
        <div className="chart-container">
          <h3>Request Distribution</h3>
          <PieChart data={chartData} />
        </div>
        
        <div className="chart-container">
          <h3>Response Time Comparison</h3>
          <BarChart data={{
            labels: Object.keys(metrics.providers),
            datasets: [{
              label: 'Avg Response Time (ms)',
              data: Object.values(metrics.providers).map(p => p.avg_response_time),
              backgroundColor: 'rgba(153, 102, 255, 0.6)'
            }]
          }} />
        </div>
      </div>
      
      <div className="provider-details">
        <h3>Provider Details</h3>
        <table>
          <thead>
            <tr>
              <th>Provider</th>
              <th>Requests</th>
              <th>Tokens</th>
              <th>Cost</th>
              <th>Response Time</th>
              <th>Error Rate</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(metrics.providers).map(([name, stats]) => (
              <tr key={name}>
                <td>{name}</td>
                <td>{stats.total_requests}</td>
                <td>{stats.total_tokens.toLocaleString()}</td>
                <td>${stats.total_cost.toFixed(4)}</td>
                <td>{stats.avg_response_time.toFixed(2)}ms</td>
                <td>{stats.error_rate}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

## Alerting System

### Threshold-Based Alerts
```python
# core/mascarade/metrics/alerts.py
class MetricsAlertSystem:
    """Alert system for metrics thresholds"""
    
    def __init__(self, tracker: MetricsTracker):
        self.tracker = tracker
        self.alerts = []
        
        # Default thresholds
        self.thresholds = {
            'error_rate': 0.1,  # 10%
            'response_time': 5.0,  # 5 seconds
            'cost_per_request': 0.5  # $0.50 per request
        }
    
    def check_alerts(self) -> list:
        """Check all providers against thresholds"""
        alerts = []
        
        for provider_name, metrics in self.tracker.providers.items():
            # Error rate alert
            if metrics.error_rate > self.thresholds['error_rate']:
                alerts.append({
                    'type': 'error_rate',
                    'provider': provider_name,
                    'value': metrics.error_rate,
                    'threshold': self.thresholds['error_rate'],
                    'severity': 'high'
                })
            
            # Response time alert
            if metrics.avg_response_time > self.thresholds['response_time']:
                alerts.append({
                    'type': 'response_time',
                    'provider': provider_name,
                    'value': metrics.avg_response_time,
                    'threshold': self.thresholds['response_time'],
                    'severity': 'medium'
                })
        
        self.alerts = alerts
        return alerts
    
    def get_active_alerts(self) -> list:
        """Get current active alerts"""
        return self.alerts
    
    def set_threshold(self, metric: str, value: float):
        """Update alert threshold"""
        self.thresholds[metric] = value
```

## Best Practices

1. **Performance Impact**: Keep metrics tracking lightweight
2. **Data Retention**: Implement history limits to prevent memory issues
3. **Privacy**: Avoid storing sensitive data in metrics
4. **Sampling**: For high-volume systems, consider sampling requests
5. **Real-time**: Update dashboard in real-time for monitoring
6. **Alerting**: Set up alerts for abnormal patterns
7. **Export**: Allow metrics export for external analysis
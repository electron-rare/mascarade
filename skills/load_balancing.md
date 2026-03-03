# Load Balancing System

## Overview
Advanced load balancing for LLM providers to distribute requests efficiently and prevent overload.

## Core Load Balancer

### File: `core/mascarade/load_balancer/balancer.py`
```python
from typing import Dict, List, Optional
from dataclasses import dataclass
import time
import random
from collections import deque

@dataclass
class ProviderStats:
    """Real-time statistics for a provider"""
    name: str
    current_load: int = 0
    pending_requests: int = 0
    last_used: float = 0
    response_times: deque = deque(maxlen=100)
    error_count: int = 0
    
    def avg_response_time(self) -> float:
        """Calculate average response time"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def error_rate(self) -> float:
        """Calculate error rate"""
        total = self.current_load + self.pending_requests
        return self.error_count / total if total > 0 else 0.0

class LoadBalancer:
    """Intelligent load balancer for LLM providers"""
    
    def __init__(self):
        self.providers: Dict[str, ProviderStats] = {}
        self.request_queue: Dict[str, deque] = {}
        self.last_update = time.time()
    
    def register_provider(self, provider_name: str):
        """Register a new provider"""
        if provider_name not in self.providers:
            self.providers[provider_name] = ProviderStats(provider_name)
            self.request_queue[provider_name] = deque()
    
    def select_provider(
        self,
        available_providers: List[str],
        strategy: str = 'round_robin'
    ) -> Optional[str]:
        """Select best provider based on load balancing strategy"""
        
        if not available_providers:
            return None
        
        # Filter to registered providers
        candidates = [p for p in available_providers if p in self.providers]
        
        if not candidates:
            return random.choice(available_providers)
        
        if strategy == 'round_robin':
            return self._round_robin(candidates)
        elif strategy == 'least_connections':
            return self._least_connections(candidates)
        elif strategy == 'fastest_response':
            return self._fastest_response(candidates)
        elif strategy == 'least_errors':
            return self._least_errors(candidates)
        elif strategy == 'weighted':
            return self._weighted_random(candidates)
        else:
            return random.choice(candidates)
    
    def _round_robin(self, candidates: List[str]) -> str:
        """Round robin selection"""
        # Find provider with oldest last_used time
        return min(candidates, key=lambda p: self.providers[p].last_used)
    
    def _least_connections(self, candidates: List[str]) -> str:
        """Select provider with least active connections"""
        return min(candidates, key=lambda p: self.providers[p].current_load)
    
    def _fastest_response(self, candidates: List[str]) -> str:
        """Select provider with fastest average response time"""
        return min(candidates, key=lambda p: self.providers[p].avg_response_time())
    
    def _least_errors(self, candidates: List[str]) -> str:
        """Select provider with lowest error rate"""
        return min(candidates, key=lambda p: self.providers[p].error_rate())
    
    def _weighted_random(self, candidates: List[str]) -> str:
        """Weighted random selection based on performance"""
        
        # Calculate weights (inverse of load and response time)
        weights = []
        total_weight = 0
        
        for provider in candidates:
            stats = self.providers[provider]
            
            # Weight based on load, response time, and error rate
            load_factor = 1.0 / (stats.current_load + 1)
            time_factor = 1.0 / (stats.avg_response_time() + 0.1)
            error_factor = 1.0 - stats.error_rate()
            
            weight = load_factor * time_factor * error_factor
            weights.append(weight)
            total_weight += weight
        
        # Normalize weights
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        
        # Weighted random selection
        rand = random.random()
        cumulative = 0
        for i, weight in enumerate(weights):
            cumulative += weight
            if rand <= cumulative:
                return candidates[i]
        
        return candidates[-1]
    
    def request_started(self, provider_name: str):
        """Notify balancer that request has started"""
        if provider_name in self.providers:
            self.providers[provider_name].pending_requests += 1
            self.providers[provider_name].last_used = time.time()
    
    def request_completed(
        self,
        provider_name: str,
        response_time: float,
        success: bool
    ):
        """Notify balancer that request has completed"""
        if provider_name in self.providers:
            stats = self.providers[provider_name]
            stats.pending_requests = max(0, stats.pending_requests - 1)
            stats.current_load = max(0, stats.current_load - 1)
            stats.response_times.append(response_time)
            
            if not success:
                stats.error_count += 1
    
    def get_load_stats(self) -> dict:
        """Get current load balancing statistics"""
        
        return {
            'providers': {
                name: {
                    'current_load': stats.current_load,
                    'pending_requests': stats.pending_requests,
                    'avg_response_time': stats.avg_response_time(),
                    'error_rate': stats.error_rate(),
                    'last_used': stats.last_used
                }
                for name, stats in self.providers.items()
            },
            'total_requests': sum(stats.current_load for stats in self.providers.values()),
            'total_pending': sum(stats.pending_requests for stats in self.providers.values())
        }
    
    def reset_stats(self):
        """Reset all load balancing statistics"""
        for stats in self.providers.values():
            stats.current_load = 0
            stats.pending_requests = 0
            stats.response_times.clear()
            stats.error_count = 0
```

## Adaptive Load Balancing

### Dynamic Weight Adjustment
```python
# core/mascarade/load_balancer/adaptive.py
class AdaptiveLoadBalancer(LoadBalancer):
    """Load balancer that adapts to changing conditions"""
    
    def __init__(self):
        super().__init__()
        self.performance_history = {}
        self.adjustment_interval = 60  # seconds
        self.last_adjustment = time.time()
    
    def _calculate_performance_score(self, provider_name: str) -> float:
        """Calculate comprehensive performance score"""
        
        stats = self.providers.get(provider_name)
        if not stats:
            return 0.0
        
        # Get historical data
        history = self.performance_history.get(provider_name, {})
        
        # Current metrics
        current_load = stats.current_load
        avg_response = stats.avg_response_time()
        error_rate = stats.error_rate()
        
        # Historical trends
        load_trend = history.get('load_trend', 0)
        time_trend = history.get('time_trend', 0)
        
        # Calculate score (0-100)
        load_score = max(0, 100 - (current_load * 10))
        time_score = max(0, 100 - (avg_response * 10))
        error_score = max(0, 100 - (error_rate * 100))
        
        trend_score = (load_trend + time_trend) * 5
        
        return (load_score * 0.4) + (time_score * 0.3) + \
               (error_score * 0.2) + (trend_score * 0.1)
    
    def _update_performance_history(self):
        """Update performance trends"""
        
        current_time = time.time()
        if current_time - self.last_adjustment < self.adjustment_interval:
            return
        
        for provider_name, stats in self.providers.items():
            if provider_name not in self.performance_history:
                self.performance_history[provider_name] = {
                    'load_history': [],
                    'time_history': [],
                    'load_trend': 0,
                    'time_trend': 0
                }
            
            history = self.performance_history[provider_name]
            
            # Update history
            history['load_history'].append(stats.current_load)
            history['time_history'].append(stats.avg_response_time())
            
            # Keep history size manageable
            if len(history['load_history']) > 10:
                history['load_history'].pop(0)
                history['time_history'].pop(0)
            
            # Calculate trends (simple linear regression)
            if len(history['load_history']) >= 2:
                x = list(range(len(history['load_history'])))
                y_load = history['load_history']
                y_time = history['time_history']
                
                history['load_trend'] = self._calculate_trend(x, y_load)
                history['time_trend'] = self._calculate_trend(x, y_time)
        
        self.last_adjustment = current_time
    
    def _calculate_trend(self, x: list, y: list) -> float:
        """Calculate trend using linear regression"""
        
        n = len(x)
        if n < 2:
            return 0.0
        
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        
        # Slope (trend)
        numerator = n * sum_xy - sum_x * sum_y
        denominator = n * sum_x2 - sum_x ** 2
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        return slope
    
    def select_provider(
        self,
        available_providers: List[str],
        strategy: str = 'adaptive'
    ) -> Optional[str]:
        """Adaptive provider selection"""
        
        # Update performance history
        self._update_performance_history()
        
        if strategy == 'adaptive':
            return self._adaptive_selection(available_providers)
        
        return super().select_provider(available_providers, strategy)
    
    def _adaptive_selection(self, candidates: List[str]) -> str:
        """Select provider based on comprehensive performance"""
        
        # Calculate scores for all candidates
        scores = []
        for provider in candidates:
            score = self._calculate_performance_score(provider)
            scores.append((provider, score))
        
        # Select provider with highest score
        if scores:
            return max(scores, key=lambda x: x[1])[0]
        
        return random.choice(candidates) if candidates else None
```

## Integration with Router

### Load-Balanced Router
```python
# core/mascarade/router/load_balanced.py
from ..load_balancer.balancer import LoadBalancer
from ..load_balancer.adaptive import AdaptiveLoadBalancer

class LoadBalancedRouter:
    """Router with load balancing capabilities"""
    
    def __init__(self, primary_router, use_adaptive: bool = True):
        self.router = primary_router
        self.balancer = AdaptiveLoadBalancer() if use_adaptive else LoadBalancer()
        
        # Register all available providers
        for provider in self.router.available_providers:
            self.balancer.register_provider(provider)
    
    async def send(
        self,
        messages: list[dict],
        **kwargs
    ) -> LLMResponse:
        """Send request with load balancing"""
        
        # Get available providers
        available = self.router.available_providers
        
        if not available:
            raise RuntimeError("No available providers")
        
        # Select provider using load balancer
        strategy = kwargs.get('load_balance_strategy', 'adaptive')
        selected_provider = self.balancer.select_provider(available, strategy)
        
        if not selected_provider:
            raise RuntimeError("Load balancer could not select provider")
        
        # Notify balancer that request is starting
        self.balancer.request_started(selected_provider)
        
        try:
            # Update kwargs to use selected provider
            kwargs['provider'] = selected_provider
            
            start_time = time.time()
            response = await self.router.send(messages, **kwargs)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Notify balancer of successful completion
            self.balancer.request_completed(
                selected_provider,
                response_time,
                success=True
            )
            
            return response
            
        except Exception as e:
            # Notify balancer of failure
            self.balancer.request_completed(
                selected_provider,
                response_time=time.time() - start_time,
                success=False
            )
            raise
    
    async def stream(
        self,
        messages: list[dict],
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream with load balancing"""
        
        available = self.router.available_providers
        
        if not available:
            raise RuntimeError("No available providers")
        
        # For streaming, we use a simpler approach
        # Select provider and stick with it for the stream
        selected_provider = self.balancer.select_provider(available, 'round_robin')
        
        if not selected_provider:
            raise RuntimeError("Load balancer could not select provider")
        
        self.balancer.request_started(selected_provider)
        
        try:
            kwargs['provider'] = selected_provider
            
            async for chunk in self.router.stream(messages, **kwargs):
                yield chunk
            
            self.balancer.request_completed(selected_provider, 0, success=True)
            
        except Exception as e:
            self.balancer.request_completed(selected_provider, 0, success=False)
            raise
    
    def get_load_stats(self) -> dict:
        """Get current load balancing statistics"""
        return self.balancer.get_load_stats()
    
    def reset_load_stats(self):
        """Reset load balancing statistics"""
        self.balancer.reset_stats()
```

## API Endpoints

### Load Balancing API
```typescript
// api/src/routes/load_balancer.ts
import { Hono } from 'hono'
import { z } from 'zod'
import { zValidator } from '@hono/zod-validator'

const app = new Hono()

// Get load balancing statistics
app.get('/load-balancer/stats', async (c) => {
  try {
    const stats = await coreClient.getLoadBalancerStats()
    return c.json(stats)
  } catch (error) {
    return c.json({ error: 'Failed to fetch load balancer stats' }, 500)
  }
})

// Configure load balancing strategy
const strategySchema = z.object({
  strategy: z.enum(['round_robin', 'least_connections', 'fastest_response', 
                    'least_errors', 'weighted', 'adaptive'])
})

app.post('/load-balancer/strategy', 
         zValidator('json', strategySchema), 
         async (c) => {
  const { strategy } = c.req.valid('json')
  
  try {
    await coreClient.setLoadBalancerStrategy(strategy)
    return c.json({ success: true, strategy })
  } catch (error) {
    return c.json({ error: 'Failed to set load balancer strategy' }, 500)
  }
})

// Reset load balancer statistics
app.post('/load-balancer/reset', async (c) => {
  try {
    await coreClient.resetLoadBalancerStats()
    return c.json({ success: true })
  } catch (error) {
    return c.json({ error: 'Failed to reset load balancer stats' }, 500)
  }
})

// Get provider recommendations
app.get('/load-balancer/recommendations', async (c) => {
  try {
    const recommendations = await coreClient.getProviderRecommendations()
    return c.json(recommendations)
  } catch (error) {
    return c.json({ error: 'Failed to get recommendations' }, 500)
  }
})

export default app
```

## Dashboard Visualization

### Load Balancer Dashboard
```typescript
// components/LoadBalancerDashboard.tsx
import { useEffect, useState } from 'react'
import { BarChart, LineChart, PieChart } from 'react-chartjs-2'

export function LoadBalancerDashboard() {
  const [stats, setStats] = useState<any>(null)
  const [strategy, setStrategy] = useState('adaptive')
  
  useEffect(() => {
    const fetchStats = async () => {
      const response = await fetch('/api/load-balancer/stats')
      const data = await response.json()
      setStats(data)
    }
    
    fetchStats()
    const interval = setInterval(fetchStats, 5000)  // Refresh every 5s
    
    return () => clearInterval(interval)
  }, [])
  
  const handleStrategyChange = async (newStrategy: string) => {
    await fetch('/api/load-balancer/strategy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy: newStrategy })
    })
    setStrategy(newStrategy)
  }
  
  if (!stats) return <div>Loading load balancer data...</div>
  
  const providers = Object.keys(stats.providers)
  
  return (
    <div className="load-balancer-dashboard">
      <h2>Load Balancer Dashboard</h2>
      
      <div className="strategy-selector">
        <label>Strategy: </label>
        <select value={strategy} onChange={(e) => handleStrategyChange(e.target.value)}>
          <option value="round_robin">Round Robin</option>
          <option value="least_connections">Least Connections</option>
          <option value="fastest_response">Fastest Response</option>
          <option value="least_errors">Least Errors</option>
          <option value="weighted">Weighted Random</option>
          <option value="adaptive">Adaptive</option>
        </select>
      </div>
      
      <div className="summary-cards">
        <div className="card">
          <h3>Total Requests</h3>
          <p>{stats.total_requests}</p>
        </div>
        <div className="card">
          <h3>Pending Requests</h3>
          <p>{stats.total_pending}</p>
        </div>
        <div className="card">
          <h3>Active Providers</h3>
          <p>{providers.length}</p>
        </div>
      </div>
      
      <div className="charts">
        <div className="chart-container">
          <h3>Current Load Distribution</h3>
          <BarChart data={{
            labels: providers,
            datasets: [{
              label: 'Current Load',
              data: providers.map(p => stats.providers[p].current_load),
              backgroundColor: 'rgba(54, 162, 235, 0.6)'
            }]
          }} />
        </div>
        
        <div className="chart-container">
          <h3>Response Time Comparison</h3>
          <BarChart data={{
            labels: providers,
            datasets: [{
              label: 'Avg Response Time (ms)',
              data: providers.map(p => stats.providers[p].avg_response_time),
              backgroundColor: 'rgba(75, 192, 192, 0.6)'
            }]
          }} />
        </div>
      </div>
      
      <div className="provider-table">
        <h3>Provider Details</h3>
        <table>
          <thead>
            <tr>
              <th>Provider</th>
              <th>Current Load</th>
              <th>Pending</th>
              <th>Response Time</th>
              <th>Error Rate</th>
              <th>Last Used</th>
            </tr>
          </thead>
          <tbody>
            {providers.map(provider => {
              const pStats = stats.providers[provider]
              return (
                <tr key={provider}>
                  <td>{provider}</td>
                  <td>{pStats.current_load}</td>
                  <td>{pStats.pending_requests}</td>
                  <td>{pStats.avg_response_time.toFixed(2)}ms</td>
                  <td>{(pStats.error_rate * 100).toFixed(2)}%</td>
                  <td>{new Date(pStats.last_used * 1000).toLocaleTimeString()}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

## Best Practices

1. **Strategy Selection**: Choose appropriate strategy for workload
2. **Monitoring**: Track load metrics in real-time
3. **Adaptive Approach**: Use adaptive balancing for dynamic conditions
4. **Health Checks**: Regular provider health monitoring
5. **Circuit Breakers**: Integrate with circuit breaker pattern
6. **Metrics Integration**: Track load balancing effectiveness
7. **Configuration**: Make strategies configurable
8. **Fallback**: Ensure fallback when all providers are busy
9. **Resource Limits**: Prevent any single provider from being overwhelmed
10. **Testing**: Test under various load conditions
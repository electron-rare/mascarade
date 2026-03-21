# Domain-Aware Intelligent Routing - Manual E2E Verification

This document provides step-by-step instructions for manually verifying the domain-aware intelligent routing feature with a live Ollama service.

## Prerequisites

1. **Ollama Service Running**
   ```bash
   # Start Ollama service
   ollama serve
   ```

2. **Load mascarade-* Models**
   ```bash
   # Load the domain-specific models
   ollama pull mascarade-kicad   # or your custom fine-tuned model
   ollama pull mascarade-spice
   ollama pull mascarade-freecad
   ollama pull mascarade-iot
   ```

3. **Configure API Keys** (for fallback testing)
   ```bash
   export ANTHROPIC_API_KEY="your-key"
   # or
   export OPENAI_API_KEY="your-key"
   ```

## Verification Steps

### Step 1: Verify Ollama Service

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Expected: JSON response with list of loaded models
```

### Step 2: Test Domain Detection

```bash
cd core
source .venv/bin/activate
python3 -c "
from mascarade.router.domain_detector import DomainDetector
detector = DomainDetector()

test_cases = [
    ('How do I route PCB traces in KiCad?', 'kicad'),
    ('Create a SPICE simulation for a RC circuit', 'spice'),
    ('Design a parametric model in FreeCAD', 'freecad'),
    ('Configure STM32 UART with HAL library', 'stm32'),
    ('Set up MQTT on ESP32 with Arduino', 'iot'),
]

for query, expected in test_cases:
    detected = detector.detect_domain(query)
    status = '✓' if detected == expected else '✗'
    print(f'{status} {query[:40]}... -> {detected} (expected: {expected})')
"
```

**Expected Output:**
```
✓ How do I route PCB traces in KiCad?... -> kicad (expected: kicad)
✓ Create a SPICE simulation for a RC c... -> spice (expected: spice)
✓ Design a parametric model in FreeCAD... -> freecad (expected: freecad)
✓ Configure STM32 UART with HAL librar... -> stm32 (expected: stm32)
✓ Set up MQTT on ESP32 with Arduino... -> iot (expected: iot)
```

### Step 3: Test Domain Routing to Ollama

```bash
python3 -c "
import asyncio
from mascarade.router import Router
from mascarade.router.router import Strategy

async def test():
    router = Router()

    # KiCad query
    messages = [{'role': 'user', 'content': 'How do I create a footprint in KiCad?'}]
    response = await router.send(
        messages,
        strategy=Strategy.DOMAIN,
        domain='kicad',
        model='mascarade-kicad',
        max_tokens=100
    )

    print(f'Provider: {response.provider}')
    print(f'Model: {response.model}')
    print(f'Response: {response.content[:100]}...')

    assert response.provider == 'ollama', f'Expected ollama, got {response.provider}'
    print('✓ KiCad query routed to Ollama')

asyncio.run(test())
"
```

**Expected Output:**
```
Provider: ollama
Model: mascarade-kicad
Response: To create a footprint in KiCad...
✓ KiCad query routed to Ollama
```

### Step 4: Test All Domains

```bash
python3 -c "
import asyncio
from mascarade.router import Router
from mascarade.router.router import Strategy
from mascarade.router.domain_detector import DomainDetector

async def test():
    router = Router()
    detector = DomainDetector()

    test_cases = [
        ('KiCad PCB routing', 'kicad'),
        ('SPICE circuit simulation', 'spice'),
        ('FreeCAD parametric design', 'freecad'),
        ('STM32 HAL configuration', 'stm32'),
        ('ESP32 MQTT setup', 'iot'),
    ]

    for query, domain in test_cases:
        messages = [{'role': 'user', 'content': query}]
        model = detector.get_model_for_domain(domain)

        response = await router.send(
            messages,
            strategy=Strategy.DOMAIN,
            domain=domain,
            model=model,
            max_tokens=50
        )

        print(f'✓ Domain {domain:8} -> provider={response.provider:10} model={response.model}')

asyncio.run(test())
"
```

**Expected Output:**
```
✓ Domain kicad    -> provider=ollama      model=mascarade-kicad
✓ Domain spice    -> provider=ollama      model=mascarade-spice
✓ Domain freecad  -> provider=ollama      model=mascarade-freecad
✓ Domain stm32    -> provider=ollama      model=mascarade-iot
✓ Domain iot      -> provider=ollama      model=mascarade-iot
```

### Step 5: Test Langfuse Trace Metadata

```bash
# Check that domain metadata is included in Langfuse traces
# This requires Langfuse to be configured
python3 -c "
import asyncio
from mascarade.router import Router
from mascarade.router.router import Strategy

async def test():
    router = Router()

    messages = [{'role': 'user', 'content': 'Design a PCB in KiCad'}]
    response = await router.send(
        messages,
        strategy=Strategy.DOMAIN,
        domain='kicad',
        model='mascarade-kicad',
        max_tokens=50
    )

    print('✓ Check Langfuse dashboard for trace with metadata:')
    print('  - strategy: domain')
    print('  - domain: kicad')
    print('  - domain_routing: True')
    print('  - domain_detected: kicad')

asyncio.run(test())
"
```

### Step 6: Test Fallback to Cloud Providers

```bash
# Stop Ollama service
# pkill ollama

# Run query with DOMAIN strategy
python3 -c "
import asyncio
from mascarade.router import Router
from mascarade.router.router import Strategy

async def test():
    router = Router()

    messages = [{'role': 'user', 'content': 'How do I route PCB traces in KiCad?'}]
    response = await router.send(
        messages,
        strategy=Strategy.DOMAIN,
        domain='kicad',
        max_tokens=50
    )

    print(f'Provider: {response.provider}')
    print(f'Model: {response.model}')

    if response.provider != 'ollama':
        print(f'✓ Fallback activated to {response.provider}')
    else:
        print('✗ Expected fallback but got Ollama')

asyncio.run(test())
"

# Restart Ollama
# ollama serve
```

**Expected Output:**
```
Provider: claude
Model: claude-3.5-sonnet
✓ Fallback activated to claude
```

### Step 7: Verify Performance

```bash
python3 -c "
import time
from mascarade.router.domain_detector import DomainDetector

detector = DomainDetector()
query = 'How do I design a complex PCB in KiCad with multiple layers and advanced routing?'

# Warm-up
detector.detect_domain(query)

# Measure
iterations = 100
start = time.perf_counter()
for _ in range(iterations):
    detector.detect_domain(query)
elapsed = (time.perf_counter() - start) * 1000

avg_time = elapsed / iterations
status = '✓' if avg_time < 50 else '✗'
print(f'{status} Average detection time: {avg_time:.2f}ms (target: <50ms)')
"
```

**Expected Output:**
```
✓ Average detection time: 0.01ms (target: <50ms)
```

## Automated Verification

Run the automated E2E verification script:

```bash
cd core
source .venv/bin/activate
python3 scripts/verify_domain_routing_e2e.py
```

## Acceptance Criteria Checklist

- [x] Queries about KiCad route to mascarade-kicad model
- [x] Queries about SPICE route to mascarade-spice model
- [x] Queries about FreeCAD route to mascarade-freecad model
- [x] Queries about STM32/IoT route to mascarade-iot model
- [x] Domain detection uses keyword matching with <50ms overhead
- [x] DOMAIN strategy available alongside best/cheapest/fastest/specific
- [x] Domain routing falls back to cloud providers when Ollama unavailable
- [x] Domain routing preferences configurable per-agent
- [x] Routing decisions logged in Langfuse traces with domain metadata

## Known Limitations

1. **SOCKS Proxy**: If you're behind a SOCKS proxy, install socksio:
   ```bash
   pip install httpx[socks]
   ```

2. **API Keys**: Cloud provider fallback requires valid API keys for Claude, OpenAI, etc.

3. **Model Availability**: mascarade-* models must be loaded in Ollama for domain routing to work.

## Troubleshooting

### Ollama Connection Error
```
Error: connection refused to localhost:11434
```
**Solution:** Start Ollama service with `ollama serve`

### Model Not Found
```
Error: model 'mascarade-kicad' not found
```
**Solution:** Load the model with `ollama pull mascarade-kicad`

### No Providers Configured
```
Error: Aucun provider LLM configuré
```
**Solution:** Set API keys for at least one cloud provider (Claude, OpenAI, etc.)

### SOCKS Proxy Error
```
Error: Using SOCKS proxy, but the 'socksio' package is not installed
```
**Solution:** `pip install httpx[socks]`

# Mascarade P2P Network - Complete Guide

## Overview

The Mascarade P2P Network enables decentralized execution of LLM and MCP tasks across multiple machines without a central coordinator. Each machine acts as both a client and server, automatically discovering peers and distributing workloads based on capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Mascarade P2P Network                           │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│  Peer A      │  Peer B     │  Peer C     │  Peer D     │  Peer E     │
│ (LLM Node)   │ (MCP Node)  │ (Hybrid)    │ (Storage)   │ (Gateway)   │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
       │             │             │             │             │
       ▼             ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         P2P Service Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ Service     │  │ Capability │  │ Task        │  │ Data        │  │
│  │ Discovery   │  │ Exchange   │  │ Distribution│  │ Sync        │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
       │             │             │             │             │
       ▼             ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         P2P Transport Layer                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│  │ libp2p  │  │ IPFS   │  │ DHT     │  │ PubSub  │  │ NAT     │    │
│  │ (Core)  │  │ (Data) │  │ (Routing)│  │ (Gossip)│  │ Traversal│    │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip jq netcat-openbsd avahi-daemon

# Install Python dependencies
pip install -r requirements.txt

# Install IPFS (optional but recommended)
wget https://dist.ipfs.tech/go-ipfs/v0.12.2/go-ipfs_v0.12.2_linux-amd64.tar.gz
 tar -xzvf go-ipfs_v0.12.2_linux-amd64.tar.gz
cd go-ipfs
sudo ./install.sh
cd ..
ipfs init
```

### 2. Configure Your Machine

```bash
# Using the TUI (recommended)
python3 scripts/machine_setup_tui.py

# Or using the Bash script
./scripts/machine_setup.sh

# Or manually edit the configuration
nano ~/.mascarade.env
```

### 3. Start the Network

```bash
# Start as a service (recommended)
sudo ./install_service.sh
sudo systemctl start mascarade-p2p

# Or run manually
./start_p2p_network.sh
```

### 4. Verify Connectivity

```bash
# Check service status
sudo systemctl status mascarade-p2p

# View logs
sudo journalctl -u mascarade-p2p -f

# Check discovered peers
./scripts/network_discovery.sh
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Machine identity
MASCARADE_MACHINE_NAME="my-machine"
MASCARADE_ALIASES="my-machine,localhost"
MASCARADE_CAPABILITIES="llm-host,docker-runtime,observability"

# Network
MASCARADE_P2P_PORT=4001
MASCARADE_IPFS_ENABLED=true
MASCARADE_BROADCAST_ADDR=255.255.255.251

# Services
MASCARADE_LLM_MODELS="mistral-7b,llama-2-7b"
MASCARADE_MCP_SERVICES="kicad-validation,nexar-api"
MASCARADE_OTEL_ENABLED=true
MASCARADE_DIFY_ENABLED=false
```

### Machine Profiles

Edit `docs/MACHINE_PROFILES.json`:

```json
{
  "machines": {
    "photon-machine": {
      "aliases": ["photon-machine", "localhost"],
      "capabilities": ["docker-runtime", "observability-local", "llm-host"],
      "p2p": {
        "peer_id": "Qm...",
        "listen_addrs": ["/ip4/0.0.0.0/tcp/4001"],
        "llm_models": ["mistral-7b"],
        "mcp_services": ["kicad-validation"]
      }
    }
  }
}
```

## Core Components

### 1. Service Discovery

Automatically finds and announces services on the network:

```bash
# Discover services
./scripts/network_discovery.sh

# Announce your services
python3 -c "
from services.p2p_service_discovery import P2PServiceDiscovery
from p2p_network import MascaradeP2PNode
import asyncio

async def main():
    node = MascaradeP2PNode()
    await node.start()
    discovery = P2PServiceDiscovery(node)
    await discovery.register_local_service('llm-inference', {
        'models': ['mistral-7b'],
        'capabilities': ['text-generation']
    })

asyncio.run(main())
"
```

### 2. Capability Exchange

Machines advertise and discover capabilities:

```python
from services.p2p_capability_exchange import P2PCapabilityExchange

# Advertise capabilities
capabilities = ['llm-host', 'docker-runtime', 'observability']
await exchange.advertise_capabilities(capabilities)

# Find peers with specific capability
peers = await exchange.request_capability('kicad-host')
```

### 3. Task Distribution

Automatically route tasks to capable machines:

```python
from services.p2p_task_distribution import P2PTaskDistribution

# Distribute a task
task_data = {
    'model': 'mistral-7b',
    'prompt': 'Hello world',
    'max_tokens': 100
}
await distributor.distribute_task('task-123', task_data, 'text-generation')
```

### 4. Observability

Distributed metrics and logging:

```python
from services.p2p_observability import P2PObservability

# Broadcast metrics
metrics = {
    'llm.inference.count': 42,
    'llm.inference.latency_ms': 150
}
await observability.broadcast_metrics(metrics)

# Collect network metrics
network_metrics = await observability.collect_network_metrics()
```

## Service Management

### Systemd Service

```bash
# Start service
sudo systemctl start mascarade-p2p

# Stop service
sudo systemctl stop mascarade-p2p

# Restart service
sudo systemctl restart mascarade-p2p

# View status
sudo systemctl status mascarade-p2p

# View logs
sudo journalctl -u mascarade-p2p -f

# Enable at boot
sudo systemctl enable mascarade-p2p
```

### Configuration Management

```bash
# Show current configuration
./config_manager.sh show

# Edit configuration
./config_manager.sh edit

# Set specific value
./config_manager.sh set CAPABILITIES "llm-host,docker-runtime"

# Generate template
./config_manager.sh generate my_config.env
```

## Network Topologies

### 1. Simple Peer-to-Peer

```
Machine A ↔ Machine B
```

### 2. Mesh Network

```
Machine A ↔ Machine B ↔ Machine C
  ↖↗      ↖↗      ↖↗
Machine D ↔ Machine E ↔ Machine F
```

### 3. Hybrid (Mesh + Gateway)

```
[Internet]
   │
[Gateway] ←→ [Mesh Network]
   │
[External Services]
```

## Security Considerations

### 1. Authentication

- Each peer has a unique PeerID (libp2p identity)
- Mutual TLS is used for encrypted communication
- Capabilities are self-declared but can be verified

### 2. Authorization

- Tasks are only routed to machines with declared capabilities
- Sensitive operations require explicit opt-in
- Network segmentation recommended for production

### 3. Data Protection

- End-to-end encryption for sensitive data
- IPFS for content-addressed storage
- Local encryption of secrets

## Performance Tuning

### Network Configuration

```bash
# Increase P2P connections
MASCARADE_P2P_CONNECTIONS=100

# Adjust discovery interval
MASCARADE_DISCOVERY_INTERVAL=15

# Enable IPFS for large data
MASCARADE_IPFS_ENABLED=true
```

### Resource Management

```bash
# Limit concurrent tasks
MASCARADE_MAX_CONCURRENT_TASKS=4

# Task timeout
MASCARADE_TASK_TIMEOUT=300

# Memory limits
MASCARADE_MAX_MEMORY_MB=4096
```

## Troubleshooting

### Common Issues

**1. Peers not discovered:**
- Check firewall rules (`ufw allow 4001/tcp`)
- Verify mDNS/avahi is running (`sudo systemctl start avahi-daemon`)
- Check network connectivity

**2. Service fails to start:**
```bash
# Check logs
sudo journalctl -u mascarade-p2p -n 50

# Test manually
python3 p2p_network.py --debug
```

**3. Capability mismatch:**
```bash
# Verify advertised capabilities
./scripts/current_machine_context.sh --json

# Check peer capabilities
./scripts/machine_lot_matrix.sh
```

### Debug Commands

```bash
# Test P2P connectivity
python3 -c "
from p2p_network import MascaradeP2PNode
import asyncio

async def test():
    node = MascaradeP2PNode()
    await node.start()
    peers = await node.discover_peers()
    print(f'Found {len(peers)} peers')

asyncio.run(test())
"

# Test service discovery
./scripts/network_discovery.sh --debug

# Test task distribution
python3 -c "
from services.p2p_task_distribution import P2PTaskDistribution
import asyncio

async def test():
    dist = P2PTaskDistribution()
    await dist.distribute_task('test-123', {'test': 'data'}, 'text-generation')

asyncio.run(test())
"
```

## Advanced Usage

### Custom Service Implementation

```python
from p2p_network import MascaradeP2PNode
import asyncio

class CustomService:
    def __init__(self):
        self.node = MascaradeP2PNode()

    async def start(self):
        await self.node.start()
        self.node.set_stream_handler("/custom/service/1.0.0", self.handle_request)

    async def handle_request(self, stream):
        data = await stream.read()
        # Process request
        response = b"Custom response"
        await stream.write(response)

    async def send_request(self, peer_id, data):
        return await self.node.send_request(peer_id, "/custom/service/1.0.0", data)

# Usage
async def main():
    service = CustomService()
    await service.start()

asyncio.run(main())
```

### Integration with Execution Hub

```bash
# Use P2P-aware execution hub
./scripts/next_useful_lot.sh --p2p-mode --json

# Chain tasks across machines
./scripts/chain_next_lot.sh --p2p-mode --start

# View P2P matrix
./scripts/machine_lot_matrix.sh --p2p-mode
```

## Deployment Scenarios

### 1. Single Machine (Development)

```bash
# Start all services on one machine
./start_p2p_network.sh
python3 scripts/execution_hub.py --machine photon-machine next --json
```

### 2. Multi-Machine (Production)

```bash
# Machine 1 (LLM Host)
./machine_setup.sh
# Select: llm-host, docker-runtime
sudo systemctl start mascarade-p2p

# Machine 2 (MCP Worker)
./machine_setup.sh
# Select: mcp-host, kicad-host
sudo systemctl start mascarade-p2p

# Machine 3 (Gateway)
./machine_setup.sh
# Select: network-online, web-server
sudo systemctl start mascarade-p2p
```

### 3. Hybrid Cloud

```bash
# On-premise machines
./machine_setup.sh --capabilities "llm-host,docker-runtime,private-network"

# Cloud machines
./machine_setup.sh --capabilities "network-online,auto-scaling,public-api"

# Connect them via gateway
./network_discovery.sh --gateway-mode
```

## Monitoring and Maintenance

### Health Checks

```bash
# Check peer health
./scripts/current_machine_context.sh --health

# Monitor network
watch -n 5 ./scripts/machine_lot_matrix.sh

# Check service status
sudo systemctl status mascarade-p2p
```

### Updates

```bash
# Pull latest changes
cd /opt/mascarade
git pull origin main

# Restart service
sudo systemctl restart mascarade-p2p

# Verify update
sudo journalctl -u mascarade-p2p -n 20
```

### Backup

```bash
# Backup configuration
sudo cp /etc/mascarade/config.env /etc/mascarade/config.env.bak

# Backup data
sudo tar -czvf mascarade_backup.tar.gz /var/lib/mascarade /etc/mascarade

# Restore
sudo tar -xzvf mascarade_backup.tar.gz -C /
```

## Roadmap

### Upcoming Features

- **Automatic Load Balancing**: Dynamic task distribution based on machine load
- **Service Mesh**: Advanced routing and retry logic
- **Secret Management**: Secure distribution of API keys and credentials
- **Federated Learning**: Distributed model training across peers
- **Geo-Replication**: Automatic data replication based on location

### Contributing

```bash
# Fork the repository
# Create a feature branch
git checkout -b feature/new-feature

# Commit changes
git commit -am "Add new feature"

# Push to branch
git push origin feature/new-feature

# Create a Pull Request
```

## Support

For issues and questions:

1. Check the [troubleshooting](#troubleshooting) section
2. Review the [configuration](#configuration) options
3. Consult the [architecture](#architecture) diagram
4. Open an issue on GitHub with:
   - Environment details
   - Configuration
   - Logs (`journalctl -u mascarade-p2p`)
   - Steps to reproduce

## License

This project is licensed under the terms of the MIT License. See LICENSE for details.

---

**Generated by Mistral Vibe**
**Last Updated:** 2024-03-09
**Version:** 1.0.0

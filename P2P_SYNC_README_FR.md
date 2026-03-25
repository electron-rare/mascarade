# Mascarade P2P Secure Sync System

## Overview

Secure peer-to-peer synchronization system for environment files and API keys using rsync with token-based authentication and public key verification.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Mascarade P2P Network                           │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│  Peer A     │  Peer B     │  Peer C     │  Peer D     │  Peer E     │
│             │             │             │             │             │
│  ┌───────┐  │             │  ┌───────┐  │             │  ┌───────┐  │
│  │ Rsync │  │             │  │ Rsync │  │             │  │ Rsync │  │
│  │ Daemon│  │             │  │ Daemon│  │             │  │ Daemon│  │
│  └───────┘  │             │  └───────┘  │             │  └───────┘  │
│             │             │             │             │             │
│  ┌───────┐  │             │  ┌───────┐  │             │  ┌───────┐  │
│  │Secrets│  │             │  │Secrets│  │             │  │Secrets│  │
│  │ Store │  │             │  │ Store │  │             │  │ Store │  │
│  └───────┘  │             │  └───────┘  │             │  └───────┘  │
└─────────────┘             └─────────────┘             └─────────────┘
       │                             │                             │
       ▼                             ▼                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                Secure Communication                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ 8-char     │  │ 32-char    │  │ AES-256    │  │            │  │
│  │ Public Key │  │ Auth Token  │  │ Encryption │  │            │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Setup

### 1. Install Dependencies

```bash
sudo apt-get update
sudo apt-get install -y rsync openssl
pip install pycryptodome
```

### 2. Deploy the System

```bash
# Make scripts executable
chmod +x p2p_sync.sh p2p_secrets_manager.sh

# Initialize directories
mkdir -p /opt/mascarade/secrets /opt/mascarade/api_keys
chmod 700 /opt/mascarade/secrets /opt/mascarade/api_keys
```

### 3. Configure Firewall

```bash
sudo ufw allow 8730/tcp
sudo ufw reload
```

## Usage

### Server Mode

Start the rsync daemon:

```bash
./p2p_sync.sh server
```

This will:
- Generate a public key (8 characters)
- Generate an auth token (32 characters)
- Start rsync daemon on port 8730
- Create configuration files

### Client Mode

Sync from a remote peer:

```bash
# First time (need to add host)
./p2p_sync.sh client remote-host.com ABCD1234 env_files

# Subsequent times (host already known)
./p2p_sync.sh client remote-host.com ABCD1234 env_files
```

Replace:
- `remote-host.com` with the remote host
- `ABCD1234` with the remote host's public key
- `env_files` with the module to sync (`env_files` or `api_keys`)

### Key Management

```bash
# Get your public key (to share with peers)
./p2p_sync.sh key

# Get auth token (for debugging)
./p2p_sync.sh token

# Stop the daemon
./p2p_sync.sh stop
```

## Security Features

### 1. Public Key System

Each peer has an 8-character public key:
- Used for initial host verification
- Shared out-of-band (manual entry)
- Stored in `known_hosts` file

### 2. Auth Token

32-character random token:
- Used for rsync authentication
- Never transmitted in clear
- Stored encrypted

### 3. Encryption

All sensitive files are encrypted:
- AES-256-CBC encryption
- Unique encryption key per installation
- Files encrypted at rest

### 4. Access Control

- Rsync modules are not world-readable
- Authentication required for all operations
- Firewall rules restrict access

## Modules

### 1. env_files

Synchronizes environment files:
- `.env` files
- Configuration files
- Machine profiles

### 2. api_keys

Synchronizes API keys:
- Service credentials
- Encrypted key files
- Access tokens

## API Key Management

```bash
# Create a new API key
./p2p_secrets_manager.sh create-key ollama

# Get an API key (temporary decrypt)
./p2p_secrets_manager.sh get-key ollama

# Encrypt a file
./p2p_secrets_manager.sh encrypt my_secret.txt

# Decrypt a file
./p2p_secrets_manager.sh decrypt my_secret.txt.enc
```

## Network Topologies

### 1. Simple Pair

```
Machine A ↔ Machine B
```

### 2. Mesh Network

```
Machine A ↔ Machine B ↔ Machine C
  ↖↗      ↖↗      ↖↗
Machine D ↔ Machine E
```

### 3. Hub-and-Spoke

```
    Machine A
   /    |    \\
Machine B Machine C Machine D
```

## Troubleshooting

### Connection Issues

```bash
# Test rsync connection
rsync -avz --port=8730 rsync://mascarade@remote-host.com/

# Check firewall
sudo ufw status

# Check rsync daemon
sudo systemctl status mascarade-p2p-sync
```

### Permission Issues

```bash
# Fix permissions
chmod 700 /opt/mascarade/secrets
chmod 600 /opt/mascarade/secrets/*
```

### Token Issues

```bash
# Regenerate tokens
rm /opt/mascarade/secrets/auth_token
./p2p_sync.sh token
```

## Best Practices

1. **Share public keys securely** (encrypted messages, secure channels)
2. **Rotate auth tokens periodically**
3. **Monitor sync logs** (`journalctl -u mascarade-p2p-sync -f`)
4. **Backup encryption keys** (without them, data cannot be decrypted)
5. **Use firewall rules** to restrict access to trusted IPs

## Integration with Mascarade

### Environment Sync

```bash
# Sync env files from peer
./p2p_sync.sh client peer1.example.com ABCD1234 env_files

# Use synced files
source /opt/mascarade/secrets/.env
```

### API Key Distribution

```bash
# Create API key on machine A
./p2p_secrets_manager.sh create-key ollama

# Sync to machine B
./p2p_sync.sh client machine-b.example.com EFGH5678 api_keys

# Use key on machine B
OLLAMA_API_KEY=$(./p2p_secrets_manager.sh get-key ollama)
```

## License

MIT License

<iframe src="https://github.com/sponsors/electron-rare/card" title="Sponsor electron-rare" height="225" width="600" style="border: 0;"></iframe>

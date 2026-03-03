# Docker Deployment

## Overview
Mascarade uses Docker Compose for deployment with separate containers for core Python services and TypeScript API.

## Docker Compose Structure

### File: `docker-compose.yml`
```yaml
version: '3.8'

services:
  core:
    build:
      context: ./core
      dockerfile: Dockerfile
    ports:
      - "8100:8100"
    environment:
      - ENV=production
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - MISTRAL_API_KEY=${MISTRAL_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    restart: unless-stopped
    volumes:
      - ./core:/app/core
    
  api:
    build:
      context: ./api
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - CORE_URL=http://core:8100
    depends_on:
      - core
    restart: unless-stopped
    
  # Optional services
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

## Core Dockerfile

### File: `core/Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY core/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY core/ ./core/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1

# Run the application
CMD ["python", "-m", "mascarade.server"]
```

## API Dockerfile

### File: `api/Dockerfile`
```dockerfile
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY api/package.json api/package-lock.json ./
RUN npm install --production

# Copy application code
COPY api/ ./

# Build the application
RUN npm run build

# Run the application
CMD ["npm", "run", "start"]
```

## Deployment Commands

### Build and Start
```bash
# From project root
docker compose build
docker compose up -d
```

### Update Services
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose up -d --build
```

### View Logs
```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f core
```

### Common Issues

#### 1. Port Conflicts
```bash
# Check running containers
netstat -tuln | grep 8100

# Kill conflicting process
kill -9 $(lsof -ti:8100)
```

#### 2. Environment Variables
```bash
# Create .env file from template
cp .env.example .env

# Edit variables
nano .env
```

#### 3. Volume Permissions
```bash
# Fix permission issues
sudo chown -R $USER:$USER ./core
```

## Production Considerations

1. **Secrets Management**: Use Docker secrets or vault for API keys
2. **Logging**: Configure proper log rotation
3. **Monitoring**: Add health checks to compose file
4. **Scaling**: Consider adding replica services
5. **Updates**: Implement blue-green deployment strategy

## Debugging

### Shell Access
```bash
# Access core container
docker compose exec core sh

# Access API container
docker compose exec api sh
```

### Test Endpoints
```bash
# Test core service
curl http://localhost:8100/health

# Test API service
curl http://localhost:3000/health
```
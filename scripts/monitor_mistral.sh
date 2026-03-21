#!/bin/bash
# monitor_mistral.sh - Monitor Mistral AI services integration

# Configuration
INTERVAL=60  # Seconds between checks
LOG_FILE="logs/mistral_monitor_$(date +%Y%m%d).log"
ALERT_THRESHOLD=5  # Number of failures before alert

# Create log directory
mkdir -p logs

echo "Starting Mistral Monitor - $(date)" | tee -a "$LOG_FILE"
echo "Interval: ${INTERVAL}s" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "----------------------------------------" | tee -a "$LOG_FILE"

# Main monitoring loop
FAILURE_COUNT=0

while true; do
    TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
    
    echo "[$TIMESTAMP] Checking Mistral services..." | tee -a "$LOG_FILE"
    
    # Check if API is reachable
    API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8100/health 2>/dev/null)
    
    if [ "$API_STATUS" != "200" ]; then
        echo "[$TIMESTAMP] ❌ API Health Check Failed: HTTP $API_STATUS" | tee -a "$LOG_FILE"
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
    else
        echo "[$TIMESTAMP] ✅ API Health Check: OK" | tee -a "$LOG_FILE"
        FAILURE_COUNT=0
    fi
    
    # Check Mistral Studio workers
    MISTRAL_STATUS=$(curl -s http://localhost:8100/scheduler/mistral/status 2>/dev/null)
    
    if [ -z "$MISTRAL_STATUS" ]; then
        echo "[$TIMESTAMP] ❌ Mistral Status Unavailable" | tee -a "$LOG_FILE"
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
    else
        WORKER_COUNT=$(echo "$MISTRAL_STATUS" | grep -o "worker" | wc -l)
        echo "[$TIMESTAMP] ✅ Mistral Workers: $WORKER_COUNT" | tee -a "$LOG_FILE"
    fi
    
    # Check metrics
    METRICS=$(curl -s http://localhost:8100/metrics 2>/dev/null)
    
    if [ -n "$METRICS" ]; then
        # Extract Mistral-specific metrics
        MISTRAL_REQUESTS=$(echo "$METRICS" | grep "mistral_requests_total" | awk '{print $2}')
        MISTRAL_LATENCY=$(echo "$METRICS" | grep "mistral_latency" | awk '{print $2}')
        MISTRAL_ERRORS=$(echo "$METRICS" | grep "mistral_errors" | awk '{print $2}')
        
        echo "[$TIMESTAMP] 📊 Requests: ${MISTRAL_REQUESTS:-0}" | tee -a "$LOG_FILE"
        echo "[$TIMESTAMP] 📊 Latency: ${MISTRAL_LATENCY:-0}ms" | tee -a "$LOG_FILE"
        echo "[$TIMESTAMP] 📊 Errors: ${MISTRAL_ERRORS:-0}" | tee -a "$LOG_FILE"
    fi
    
    # Alert if too many failures
    if [ $FAILURE_COUNT -ge $ALERT_THRESHOLD ]; then
        echo "[$TIMESTAMP] 🚨 ALERT: $FAILURE_COUNT consecutive failures!" | tee -a "$LOG_FILE"
        # Here you could add notification (email, Slack, etc.)
    fi
    
    echo "[$TIMESTAMP] ----------------------------------------" | tee -a "$LOG_FILE"
    
    # Wait for next check
    sleep $INTERVAL
done

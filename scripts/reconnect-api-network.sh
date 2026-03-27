#!/usr/bin/env bash
# Ensure mascarade-api stays connected to core network
HC_PING="https://hc.saillant.cc/ping/2b038598-50da-4fb8-afaf-09f2829158e2"
curl -fsS --retry 3 "$HC_PING/start" -o /dev/null 2>/dev/null
docker network connect mascarade-main_mascarade-network mascarade-api 2>/dev/null
curl -fsS --retry 3 "$HC_PING" -o /dev/null 2>/dev/null || true

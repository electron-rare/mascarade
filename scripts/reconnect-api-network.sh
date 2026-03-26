#!/usr/bin/env bash
# Ensure mascarade-api stays connected to core network
docker network connect mascarade-main_mascarade-network mascarade-api 2>/dev/null

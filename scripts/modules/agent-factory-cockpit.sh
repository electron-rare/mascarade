#!/usr/bin/env bash
# scripts/modules/agent-factory-cockpit.sh — Industrial cockpit operator lane

module_agent_factory_cockpit_config() {
  AGENT_FACTORY_COCKPIT_PORT=$(input_value "Port Agent Factory Cockpit" "${AGENT_FACTORY_COCKPIT_PORT:-4173}")
  AGENT_FACTORY_COCKPIT_DIR=$(input_value "Chemin agent-factory-cockpit" "${AGENT_FACTORY_COCKPIT_DIR:-/workspace/agent-factory-cockpit}")
  AGENT_FACTORY_TRUSTED_PROXY_CIDRS=$(input_value "CIDRs proxies de confiance cockpit industriel" "${AGENT_FACTORY_TRUSTED_PROXY_CIDRS:-172.16.0.0/12}")
}

module_agent_factory_cockpit_compose() {
  echo "  agent-factory-cockpit:"
  echo "    build:"
  echo "      context: ../agent-factory-cockpit"
  echo "      dockerfile: Dockerfile"
  echo "    container_name: mascarade-agent-factory-cockpit"
  echo "    restart: unless-stopped"
  echo "    env_file:"
  echo "      - .env"
  echo "    environment:"
  echo "      AGENT_FACTORY_STORAGE_ROOT: /data"
  echo "      AGENT_FACTORY_OPERATOR_GROUPS: \${AGENT_FACTORY_OPERATOR_GROUPS:-operator}"
  echo "      AGENT_FACTORY_APPROVER_GROUPS: \${AGENT_FACTORY_APPROVER_GROUPS:-approver}"
  echo "      AGENT_FACTORY_AUDITOR_GROUPS: \${AGENT_FACTORY_AUDITOR_GROUPS:-auditor}"
  echo "      AGENT_FACTORY_ADMIN_GROUPS: \${AGENT_FACTORY_ADMIN_GROUPS:-admin}"
  echo "    command:"
  echo "      - /bin/sh"
  echo "      - -lc"
  echo "      - >-"
  echo "        proxy_args=\"\";"
  echo '        OLD_IFS=$$IFS;'
  echo "        IFS=',';"
  echo "        for cidr in \${AGENT_FACTORY_TRUSTED_PROXY_CIDRS:-172.16.0.0/12}; do"
  echo '          cidr=$$(printf '"'"'%s'"'"' "$$cidr" | xargs);'
  echo '          [ -n "$$cidr" ] && proxy_args="$$proxy_args --trusted-proxy-cidr $$cidr";'
  echo "        done;"
  echo '        IFS=$$OLD_IFS;'
  echo '        exec python3 serve.py --host 0.0.0.0 --port ${AGENT_FACTORY_COCKPIT_PORT:-4173} --auth-mode proxy-auth $$proxy_args'
  echo "    expose:"
  echo "      - \"4173\""
  echo "    read_only: true"
  echo "    tmpfs:"
  echo "      - /tmp"
  echo "    cap_drop:"
  echo "      - ALL"
  echo "    security_opt:"
  echo "      - no-new-privileges:true"
  echo "    volumes:"
  echo "      - agent-factory-cockpit-data:/data"
  echo "    healthcheck:"
  echo "      test:"
  echo "        - CMD-SHELL"
  echo "        - python3 -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:4173/api/health')\""
  echo "      interval: 15s"
  echo "      timeout: 5s"
  echo "      retries: 10"
  echo "      start_period: 15s"
  echo "    networks:"
  echo "      - mascarade-network"
}

module_agent_factory_cockpit_volumes() {
  echo "  agent-factory-cockpit-data:"
  echo "    name: agent-factory-cockpit-data"
}

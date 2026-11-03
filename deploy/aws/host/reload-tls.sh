#!/usr/bin/env bash
set -euo pipefail
install -d -m 0750 -g 65532 /var/lib/signguard-edge/tls
install -m 0640 -g 65532 /etc/letsencrypt/live/signguard/fullchain.pem /var/lib/signguard-edge/tls/fullchain.pem
install -m 0640 -g 65532 /etc/letsencrypt/live/signguard/privkey.pem /var/lib/signguard-edge/tls/privkey.pem
if [[ -f /opt/signguard/current/deploy/aws/rendered/compose.yaml ]]; then
  docker compose -f /opt/signguard/current/deploy/aws/rendered/compose.yaml restart ui
fi

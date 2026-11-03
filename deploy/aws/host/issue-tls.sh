#!/usr/bin/env bash
# Approved maintenance ingress only; never run during source preparation/tests.
set -euo pipefail
public_ip="$1"
contact_email="$2"
python3 - "$public_ip" <<'PY'
import ipaddress,sys
ip=ipaddress.ip_address(sys.argv[1])
assert ip.version==4 and ip.is_global
PY
install -d -m 0755 /var/lib/signguard-edge/acme
python3 -m venv /opt/signguard/certbot
/opt/signguard/certbot/bin/pip install --disable-pip-version-check 'certbot==5.9.0'
# Temporary read-only challenge directory contains no documents, keys or application routes.
python3 -m http.server 80 --bind 0.0.0.0 --directory /var/lib/signguard-edge/acme >/var/log/signguard-acme.log 2>&1 &
challenge_pid=$!
trap 'kill "$challenge_pid" 2>/dev/null || true' EXIT
/opt/signguard/certbot/bin/certbot certonly --webroot --webroot-path /var/lib/signguard-edge/acme \
  --ip-address "$public_ip" --preferred-profile shortlived --cert-name signguard \
  --agree-tos --non-interactive --email "$contact_email"
# Never use --staging certificates or disable browser trust for a live URL.
openssl x509 -checkend 86400 -noout -in /etc/letsencrypt/live/signguard/fullchain.pem

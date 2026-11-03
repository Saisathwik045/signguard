#!/usr/bin/env bash
# Runs only as EC2 user-data after explicit account/billing approval. Never opens ingress.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg uidmap dbus-user-session python3 python3-venv awscli jq
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
printf 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' "$VERSION_CODENAME" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras
# Rootful daemon runs only trusted web/controller containers. Executor NEVER joins docker group.
groupadd --system --gid 1500 signguard-control
useradd --create-home --uid 1001 --gid 1500 --shell /bin/bash signguard-executor
usermod --lock signguard-executor
install -d /etc/systemd/system/user@.service.d
printf '[Service]\nDelegate=cpu cpuset io memory pids\n' > /etc/systemd/system/user@.service.d/delegate.conf
systemctl daemon-reload
loginctl enable-linger signguard-executor
systemctl start user@1001.service
runuser -u signguard-executor -- env XDG_RUNTIME_DIR=/run/user/1001 dockerd-rootless-setuptool.sh install --force
install -d -m 0750 -o 1001 -g 1500 /run/signguard
install -d -m 0700 /etc/signguard /var/lib/signguard-edge
install -d -m 0750 -g 1500 /opt/signguard/releases
# Block metadata access from non-root host users. Container bridges are additionally blocked by IMDS hop=1.
iptables -I OUTPUT -d 169.254.169.254/32 -m owner ! --uid-owner 0 -j REJECT
iptables -I DOCKER-USER -d 169.254.169.254/32 -j REJECT
cat > /etc/systemd/system/signguard-metadata-guard.service <<'UNIT'
[Unit]
After=docker.service
Requires=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'iptables -C OUTPUT -d 169.254.169.254/32 -m owner ! --uid-owner 0 -j REJECT || iptables -I OUTPUT -d 169.254.169.254/32 -m owner ! --uid-owner 0 -j REJECT'
ExecStart=/bin/sh -c 'iptables -C DOCKER-USER -d 169.254.169.254/32 -j REJECT || iptables -I DOCKER-USER -d 169.254.169.254/32 -j REJECT'
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable signguard-metadata-guard.service
# No application starts here. No SSH key, secret value or public upload route is installed.
printf '%s\n' 'Bootstrap complete; audit mount, pinned release, secrets, TLS and host qualification remain required.'

#!/usr/bin/env bash
# Invoked by an approved SSM command after release checksum and source validation.
set -euo pipefail
release_directory="$1"
secret_arn="$2"
region=us-east-1
cd "$release_directory"
# The source bundle MUST have been verified against the protected workflow's SHA-256 before this step.
python3 -m venv "$release_directory/executor-venv"
"$release_directory/executor-venv"/bin/pip install --no-deps . 'PyYAML==6.0.3'
# Abort until the persistent audit volume is mounted by a reviewed operator workflow.
mountpoint -q /var/lib/signguard/audit
install -d -m 0770 -o 65532 -g 65532 /var/lib/signguard/audit
aws secretsmanager get-secret-value --region "$region" --secret-id "$secret_arn" --query SecretString --output text \
 | "$release_directory/executor-venv"/bin/python scripts/write_aws_runtime_secrets.py /etc/signguard
"$release_directory/executor-venv"/bin/python scripts/render_aws_staging.py release.json deploy/aws/rendered
install -m 0644 deploy/aws/host/oauth.cfg /etc/signguard/oauth.cfg
public_ip=$(python3 -c 'import json; print(json.load(open("release.json"))["public_ipv4"])')
printf '\nOAUTH2_PROXY_REDIRECT_URL=https://%s/oauth2/callback\n' "$public_ip" >> /etc/signguard/oauth.env
# Pull reviewed digests; temporary registry credentials are removed immediately after each pull.
registry=$(python3 -c 'import json; r=json.load(open("release.json")); print(r["account_id"]+".dkr.ecr.us-east-1.amazonaws.com")')
registry_tmp=$(mktemp -d)
trap 'rm -rf "$registry_tmp"' EXIT
aws ecr get-login-password --region "$region" | docker --config "$registry_tmp" login --username AWS --password-stdin "$registry" >/dev/null
for role in ui controller; do
  image_ref=$(python3 - "$role" <<'PY'
import json,sys
print(json.load(open('release.json'))['images'][sys.argv[1]])
PY
)
  docker --config "$registry_tmp" pull --platform linux/amd64 "$image_ref" >/dev/null
done
worker_ref=$(python3 -c 'import json; print(json.load(open("release.json"))["images"]["worker"])')
executor_tmp=$(mktemp -d /home/signguard-executor/registry.XXXXXXXX)
chown 1001:1500 "$executor_tmp"
trap 'rm -rf "$registry_tmp" "$executor_tmp"' EXIT
aws ecr get-login-password --region "$region" | runuser -u signguard-executor -- docker --config "$executor_tmp" --host=unix:///run/user/1001/docker.sock login --username AWS --password-stdin "$registry" >/dev/null
runuser -u signguard-executor -- docker --config "$executor_tmp" --host=unix:///run/user/1001/docker.sock pull --platform linux/amd64 "$worker_ref" >/dev/null
rm -rf "$executor_tmp"
printf 'SIGNGUARD_WORKER_IMAGE=%s\n' "$worker_ref" > /etc/signguard/executor.env
chmod 0644 /etc/signguard/executor.env
install -m 0644 deploy/aws/host/signguard-executor.service /etc/systemd/system/
test -f /etc/letsencrypt/live/signguard/fullchain.pem
openssl x509 -checkend 86400 -noout -in /etc/letsencrypt/live/signguard/fullchain.pem
ln -sfn "$release_directory" /opt/signguard/current
systemctl daemon-reload
systemctl enable --now signguard-executor
"$release_directory/executor-venv"/bin/python scripts/aws_host_preflight.py /var/lib/signguard/host-preflight.json
docker compose -f deploy/aws/rendered/compose.yaml config --quiet
docker compose -f deploy/aws/rendered/compose.yaml up -d
# This deployment remains authenticated MAINTENANCE ONLY. It never enables uploads.

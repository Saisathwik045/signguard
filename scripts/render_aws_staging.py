"""Generate fixed, closed-by-default host wiring; release input never contains secrets."""
import argparse
import ipaddress
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def render(release, target):
    if set(release) != {"account_id", "region", "public_ipv4", "commit", "images"}:
        raise ValueError("Unexpected release fields")
    if not re.fullmatch(r"[0-9]{12}", release["account_id"]) or release["region"] != "us-east-1":
        raise ValueError("Reviewed AWS account and region required")
    address = ipaddress.ip_address(release["public_ipv4"])
    if address.version != 4 or not address.is_global:
        raise ValueError("An allocated global static IPv4 is required")
    if not re.fullmatch(r"[0-9a-f]{40}", release["commit"]):
        raise ValueError("Immutable source commit required")
    if set(release["images"]) != {"ui", "worker", "controller"}:
        raise ValueError("All service images required")
    for role, image in release["images"].items():
        expected = release['account_id']+'.dkr.ecr.us-east-1.amazonaws.com/signguard-staging-'+role
        if not re.fullmatch(re.escape(expected)+r"@sha256:[0-9a-f]{64}", image):
            raise ValueError("Only approved immutable ECR service images are accepted")
    target.mkdir(parents=True, exist_ok=True)
    edge = json.loads((ROOT / 'deploy/aws/edge-images.json').read_text())
    defaults = {"user": "65532:65532", "read_only": True, "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"], "pids_limit": 64, "cpus": 1,
                "tmpfs": ["/tmp:size=64m,noexec,nosuid,nodev"], "restart": "unless-stopped"}
    services = {
        "ui": {**defaults, "image": release['images']['ui'], "mem_limit": "1g", "networks": ["control"],
               "env_file": ["/etc/signguard/ui.env"], "environment": {
                   "SIGNGUARD_REQUIRE_AUTH": "true", "SIGNGUARD_AUTH_MODE": "gateway",
                   "SIGNGUARD_BACKEND": "broker", "SIGNGUARD_BROKER_URL": "http://controller:8080",
                   "SIGNGUARD_LIVE_UPLOADS_ENABLED": "false"}},
        "controller": {**defaults, "image": release['images']['controller'], "mem_limit": "512m",
            "networks": ["control"], "group_add": ["1500"], "env_file": ["/etc/signguard/controller.env"], "environment": {
                "SIGNGUARD_EXECUTOR_SOCKET": "/run/signguard/executor.sock",
                "SIGNGUARD_AUDIT_PATH": "/var/lib/signguard/audit.jsonl",
                "SIGNGUARD_QUOTA_DATABASE": "/var/lib/signguard/quota.sqlite3"}, "volumes": [
                    "/run/signguard:/run/signguard:ro", "/var/lib/signguard/audit:/var/lib/signguard"]},
        "oauth": {**defaults, "image": edge['oauth'], "mem_limit": "256m", "networks": ["edge", "control"],
                  "env_file": ["/etc/signguard/oauth.env"],
                  "command": ["--config=/etc/signguard/oauth.cfg"],
                  "volumes": ["/etc/signguard/oauth.cfg:/etc/signguard/oauth.cfg:ro"],
                  "extra_hosts": ["host.docker.internal:host-gateway"]},
    }
    # Host networking here belongs to trusted TLS/auth proxies only; PDF workers ALWAYS use network=none.
    services['oauth']['command'] += ["--upstream=http://ui:8501"]
    services['caddy'] = {"image": edge['caddy'], "read_only": True, "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"], "mem_limit": "128m", "pids_limit": 32, "cpus": .5,
        "networks": ["edge"], "ports": ["80:80", "443:443"], "env_file": ["/etc/signguard/edge.env"],
        "tmpfs": ["/tmp:size=16m,noexec,nosuid,nodev"], "volumes": [
            str(target.resolve()/"Caddyfile")+":/etc/caddy/Caddyfile:ro", "/etc/letsencrypt:/etc/letsencrypt:ro",
            "/var/lib/signguard-edge/acme:/srv/acme:ro", "/var/lib/signguard-edge/caddy:/data"],
        "restart": "unless-stopped"}
    (target/'compose.yaml').write_text(yaml.safe_dump({"services": services, "networks": {"control": {"internal": True}, "edge": {}}}, sort_keys=False))
    ip = str(address)
    (target/'Caddyfile').write_text('''{
    admin off
    auto_https off
}
:80 {
    handle /.well-known/acme-challenge/* {
        root * /srv/acme
        file_server
    }
    handle { respond "Unavailable" 503 }
}
https://'''+ip+''' {
    tls /etc/letsencrypt/live/signguard/fullchain.pem /etc/letsencrypt/live/signguard/privkey.pem
    request_body { max_size 30MB }
    header {
        Cache-Control "no-store"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer"
    }
    @logout path /auth/logout
    redir @logout /oauth2/sign_out 303
    reverse_proxy oauth:4180 {
        header_up -X-SignGuard-Gateway
        header_up X-SignGuard-Gateway {$SIGNGUARD_GATEWAY_TOKEN}
        header_up -Authorization
    }
}
''')
    (target/'release.json').write_text(json.dumps(release, indent=2)+'\n')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('release', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    render(json.loads(args.release.read_text()), args.output)

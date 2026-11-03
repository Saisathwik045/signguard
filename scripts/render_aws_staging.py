"""Generate fixed, closed-by-default host wiring; release input never contains secrets."""
import argparse
import ipaddress
import json
import re
from pathlib import Path

import yaml


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
    defaults = {"user": "65532:65532", "read_only": True, "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"], "pids_limit": 64, "cpus": 1,
                "tmpfs": ["/tmp:size=64m,noexec,nosuid,nodev"], "restart": "unless-stopped"}
    services = {
        "ui": {**defaults, "image": release['images']['ui'], "mem_limit": "1g", "networks": ["control", "identity"],
               "env_file": ["/etc/signguard/ui.env"],
               "entrypoint": ["python", "-m", "signguard.production_web"],
               "ports": ["443:8501"], "volumes": [
                   "/var/lib/signguard-edge/tls:/etc/signguard/tls:ro",
                   "/var/lib/signguard/audit/auth:/var/lib/signguard/auth"],
               "healthcheck": {"test": ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8502/_stcore/health',timeout=2)"], "interval":"30s", "timeout":"3s"},
               "environment": {
                   "SIGNGUARD_PUBLIC_ORIGIN": "https://"+str(address),
                   "SIGNGUARD_SESSION_DATABASE": "/var/lib/signguard/auth/sessions.sqlite3",
                   "SIGNGUARD_GITHUB_OWNER_ID": "220234042",
                   "SIGNGUARD_REQUIRE_AUTH": "true", "SIGNGUARD_AUTH_MODE": "gateway",
                   "SIGNGUARD_BACKEND": "broker", "SIGNGUARD_BROKER_URL": "http://controller:8080",
                   "SIGNGUARD_LIVE_UPLOADS_ENABLED": "false"}},
        "controller": {**defaults, "image": release['images']['controller'], "mem_limit": "512m",
            "networks": ["control"], "group_add": ["1500"], "env_file": ["/etc/signguard/controller.env"], "environment": {
                "SIGNGUARD_EXECUTOR_SOCKET": "/run/signguard/executor.sock",
                "SIGNGUARD_AUDIT_PATH": "/var/lib/signguard/audit.jsonl",
                "SIGNGUARD_QUOTA_DATABASE": "/var/lib/signguard/quota.sqlite3"}, "volumes": [
                    "/run/signguard:/run/signguard:ro", "/var/lib/signguard/audit/controller:/var/lib/signguard"]},
    }
    (target/'compose.yaml').write_text(yaml.safe_dump({"services": services, "networks": {"control": {"internal": True}, "identity": {}}}, sort_keys=False))
    (target/'release.json').write_text(json.dumps(release, indent=2)+'\n')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('release', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    render(json.loads(args.release.read_text()), args.output)

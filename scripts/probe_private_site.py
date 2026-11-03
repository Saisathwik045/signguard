"""Probe a real private origin; keep the service credential in process memory only."""
import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(origin, token, output):
    address = urlsplit(origin)
    if address.scheme != "https" or not address.hostname or address.path not in {"", "/"}:
        raise ValueError("An exact HTTPS origin is required")
    opener = urllib.request.build_opener(NoRedirect())
    checks = []
    for path in ("/", "/health.json", "/catalogue.json", "/reports/genuine_signed.json", "/app.js"):
        request = urllib.request.Request(origin.rstrip("/")+path)
        try:
            with opener.open(request, timeout=20) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        if status not in {301, 302, 303, 307, 308, 401, 403}:
            raise ValueError(f"Anonymous application access was not denied: {path}, status={status}")
        checks.append({"path": path, "anonymous_status": status, "denied": True})
    if not token:
        raise ValueError("Protected service access is unavailable")
    request = urllib.request.Request(origin.rstrip("/")+"/health.json",
                                      headers={"OAI-Sites-Authorization": "Bearer "+token})
    with opener.open(request, timeout=20) as response:
        health = json.loads(response.read(8192))
    if health.get("mode") != "synthetic-only" or health.get("uploads") is not False or health.get("backend") is not False:
        raise ValueError("Unexpected deployed health response")
    output.mkdir(parents=True, exist_ok=True)
    result = {"origin": origin, "tls_verification_enabled": True, "anonymous_checks": checks,
              "authorized_health": health, "authentication_scope": "Platform service bearer; interactive owner SSO not automated"}
    (output / "route-proof.json").write_text(json.dumps(result, indent=2)+"\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("origin")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(probe(args.origin, os.environ.get("SIGNGUARD_SITE_BEARER", ""), args.output), indent=2))

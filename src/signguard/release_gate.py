"""Fail-closed release attestation checks; no deployment/ingress is performed by this module."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

REQUIRED = ("all_routes_authentication_verified", "private_route_verified", "authentication_verified", "authorization_verified",
            "tls_verified", "restricted_executor_verified", "resource_limits_verified",
            "quotas_verified", "secrets_isolation_verified", "temporary_cleanup_verified")


def check(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "release.json").read_text())
    if any(manifest.get(key) is not True for key in REQUIRED):
        raise ValueError("Mandatory verified control is missing")
    url = urlsplit(manifest.get("preview_url", ""))
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("Verified HTTPS preview URL is required")
    artifacts = manifest.get("artifacts", {})
    for name in ("browser-junit.xml", "os-scan.json", "dependency-audit.json", "route-proof.json"):
        value = artifacts.get(name)
        if not value or hashlib.sha256((directory / name).read_bytes()).hexdigest() != value:
            raise ValueError("Missing or mismatched release evidence")
    from defusedxml import ElementTree as etree
    tests = etree.parse(directory / "browser-junit.xml").getroot()
    if any(int(node.get(key, "0")) for node in tests.iter() for key in ("failures", "errors", "skipped")):
        raise ValueError("Browser evidence contains unsuccessful checks")
    if not any(int(node.get("tests", "0")) >= 10 for node in tests.iter()):
        raise ValueError("Insufficient end-to-end test evidence")
    scan = json.loads((directory / "os-scan.json").read_text())
    if not scan.get("Results") or any(v.get("Severity") in {"HIGH", "CRITICAL"}
            for result in scan["Results"] for v in result.get("Vulnerabilities", [])):
        raise ValueError("OS image security gate failed or scan is incomplete")
    audit = json.loads((directory / "dependency-audit.json").read_text())
    if not audit.get("dependencies") or any(d.get("vulns") for d in audit["dependencies"]):
        raise ValueError("Dependency gate failed")
    route = json.loads((directory / "route-proof.json").read_text())
    if route.get("url") != manifest["preview_url"] or route.get("visibility") != "private" or route.get("authenticated_probe_passed") is not True:
        raise ValueError("Private authenticated route has not been verified")
    return {"ready_for_private_staging": True, "url": manifest["preview_url"],
            "limitation": "Trusted operator evidence is required; this validator cannot establish external identity by itself"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.evidence), indent=2))


if __name__ == "__main__":
    main()

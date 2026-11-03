"""Require a complete scan of the tested image; reject severity downgrading of original CVEs."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def verify(scan, inventory, baseline=None):
    if scan.get("Metadata", {}).get("ImageID") != inventory.get("image_id") or not inventory.get("image_id"):
        raise ValueError("Scan does not match the exact runtime image")
    if not scan.get("CreatedAt") or not scan.get("Metadata", {}).get("OS", {}).get("Family"):
        raise ValueError("OS scan is incomplete or unrecognized")
    results = scan.get("Results", [])
    if not any(r.get("Class") == "os-pkgs" and r.get("Packages") for r in results):
        raise ValueError("OS package inventory is missing")
    findings = [v for r in results for v in r.get("Vulnerabilities", [])]
    counts = dict(Counter(v["Severity"] for v in findings))
    original = {v["VulnerabilityID"] for r in (baseline or {}).get("Results", [])
                for v in r.get("Vulnerabilities", []) if v["Severity"] in {"HIGH", "CRITICAL"}}
    remaining = sorted(original & {v["VulnerabilityID"] for v in findings})
    if counts.get("HIGH", 0) or counts.get("CRITICAL", 0) or remaining:
        raise ValueError(f"Image gate failed: counts={counts}; original CVEs still reported={remaining}")
    return {"image_id": inventory["image_id"], "image_gate_passed": True, "severity_counts": counts,
            "original_high_critical_cves_remaining": remaining, "external_ingress_enabled": False,
            "deployment_readiness": "BLOCKED", "reason": "Private TLS/identity/executor/audit deployment gates remain"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("scan", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(json.loads(args.scan.read_text()), json.loads(args.inventory.read_text()),
                    json.loads(args.baseline.read_text()) if args.baseline else None)
    result["scan_sha256"] = hashlib.sha256(args.scan.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))

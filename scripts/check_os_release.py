"""Record real OS scan findings and keep external admission blocked until every gate is verified."""
import argparse
import json
import os
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("reports", nargs="+", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
findings = []
for path in args.reports:
    report = json.loads(path.read_text())
    if not report.get("Results") or not report.get("Metadata", {}).get("OS"):
        raise SystemExit("Incomplete OS scan evidence")
    findings += [v for result in report["Results"] for v in result.get("Vulnerabilities", [])]
counts = dict(Counter(v["Severity"] for v in findings))
blocked = sum(counts.get(level, 0) for level in ("HIGH", "CRITICAL"))
result = {"os_gate_passed": blocked == 0, "blocking_findings": blocked, "severity_counts": counts,
          "external_ingress_enabled": False, "reports": [p.name for p in args.reports],
          "note": "Functional CI success is not release approval; complete private-route/auth/TLS evidence is also mandatory"}
args.output.write_text(json.dumps(result, indent=2)+"\n")
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
        stream.write(f"\nRelease admission: **{'OS GATE PASSED; other gates required' if blocked == 0 else 'BLOCKED'}**. "
                     f"High/critical findings: {blocked}. No ingress was enabled.\n")
print(json.dumps(result, indent=2))

import argparse
import json
from pathlib import Path

from .pipeline import analyze_pdf


def main():
    parser = argparse.ArgumentParser(description="Offline SignGuard PDF triage")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    report = analyze_pdf(args.pdf.read_bytes(), baseline=args.baseline.read_bytes() if args.baseline else None,
                         audit_path=args.audit)
    print(json.dumps(report, indent=2))

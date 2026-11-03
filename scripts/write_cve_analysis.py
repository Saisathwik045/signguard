"""Retain every baseline high/critical finding and explain its observed disposition."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

CONTEXT = {
    "util-linux": "Mount/partition operations are not invoked by PDF analysis; mount privileges are denied. Source-package findings still counted.",
    "sqlite": "Crafted SQLite/FTS data is the trigger; SignGuard accepts PDFs, not databases. Python links SQLite, so this library was retained and replaced.",
    "zlib": "The named minizip ZIP-writing overflow is distinct from PDF Flate decoding. Distro package affectedness still governs the scan; no exception was applied.",
    "ncurses": "Terminal-processing vulnerability; the headless PDF worker does not process terminal data. Runtime libraries were still replaced.",
    "systemd": "Home-record signature verification/privilege escalation requires systemd-homed functionality, not PDF verification. Non-root and no host mounts reduce exposure.",
    "acl": "Symlink/ACL traversal requires filesystem operations; worker root is read-only with no host directories. No finding was waived on that basis.",
    "gzip": "LZH decompression is not the PDF parser's input path; the gzip CLI is not invoked. The package finding remained a baseline blocker.",
    "perl": "Crafted tar handling in Perl is not used by worker analysis; no Perl execution interface is exposed. Base-package presence was still counted.",
    "setuptools": "Full scan located setuptools 70.3.0 through pip/_vendor/bom.cdx.json (AnalyzedBy=sbom), not an installed distribution. Pip and its complete vendor tree were uninstalled from the runtime; the SBOM was not edited or excluded.",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("final", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    baseline, final, inventory = (json.loads(p.read_text()) for p in (args.baseline, args.final, args.inventory))
    current = {v["VulnerabilityID"] for r in final["Results"] for v in r.get("Vulnerabilities", [])}
    packages = {p["Name"]: p["Version"] for r in final["Results"] if r.get("Class") == "os-pkgs"
                for p in r.get("Packages", [])}
    groups = defaultdict(list)
    for result in baseline["Results"]:
        for finding in result.get("Vulnerabilities", []):
            if finding["Severity"] in {"HIGH", "CRITICAL"}:
                groups[finding["VulnerabilityID"]].append({**finding, "scan_class": result.get("Class")})
    rows = []
    for cve, findings in sorted(groups.items()):
        first = findings[0]
        context = next((value for key, value in CONTEXT.items()
                        if key in (first.get("Title", "")+first["PkgName"]).lower()),
                       "Reachability has not been independently proven; all scanner findings are counted.")
        rows.append({"cve": cve, "severity": first["Severity"], "title": first.get("Title"),
            "affected_packages": [{"name": v["PkgName"], "baseline_version": v["InstalledVersion"],
                "published_fix_in_baseline_feed": v.get("FixedVersion") or None,
                "final_os_version": packages.get(v["PkgName"]), "original_scan_class": v["scan_class"]} for v in findings],
            "exploitability_context": context, "cvss": first.get("CVSS"), "references": first.get("References"),
            "remediation": "Still reported" if cve in current else "Absent from final unfiltered scan after base replacement/tool removal",
            "original_issue_requiring_new_base": first["scan_class"] == "os-pkgs" and not first.get("FixedVersion")})
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "cve-analysis.json").write_text(json.dumps({"baseline_image_id": baseline["Metadata"]["ImageID"],
        "final_image_id": inventory["image_id"], "findings": rows,
        "limitations": "Package-version/source-feed analysis and runtime checks, not exploit reproduction or independent proof of non-reachability."}, indent=2)+"\n")
    lines = ["# Phase 6 baseline CVE disposition", "", "All original high/critical records remain in baseline-full-scan.json.",
             "OS findings: 38 package records / 13 CVEs; one additional HIGH record came from pip's embedded build SBOM.", "",
             "| CVE | Severity | Baseline affected packages | Available baseline fix | Final disposition |",
             "| --- | --- | --- | --- | --- |"]
    for row in rows:
        names = ", ".join(v["name"] for v in row["affected_packages"])
        fixes = ", ".join(sorted({v["published_fix_in_baseline_feed"] or "None published in Debian feed" for v in row["affected_packages"]}))
        lines.append(f"| {row['cve']} | {row['severity']} | {names} | {fixes} | {row['remediation']} |")
    lines += ["", "See cve-analysis.json for every affected package/version, final replacement or absence, CVSS vector, references and exploitability context.",
              "Ubuntu source-package backports/affectedness differ from Debian; numeric version comparison alone is not patch proof.",
              "No scanner scope/severity/unfixed filtering, SBOM editing or vulnerability waiver was used.", ""]
    (args.output / "CVE_ANALYSIS.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()

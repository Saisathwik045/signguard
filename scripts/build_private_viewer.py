"""Package only existing verified reports and static UI. Never parse a user PDF."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from signguard.demo import CASES, load_case

ROOT = Path(__file__).resolve().parents[1]


def build(output):
    target = output / "dist"
    if target.exists():
        shutil.rmtree(target)
    (target / "reports").mkdir(parents=True)
    for name in ("index.html", "app.js", "styles.css"):
        shutil.copyfile(ROOT / "web/private-viewer" / name, target / name)
    assets = ROOT / "src/signguard/demo_assets"
    manifest = json.loads((assets / "manifest.json").read_text())
    for case_id in CASES:
        report, _ = load_case(case_id)
        raw = (assets / (case_id+".json")).read_bytes()
        if len(raw) > 1024*1024 or not report.get("pdf_report"):
            raise ValueError("Invalid or oversized fixed report")
        (target / "reports" / (case_id+".json")).write_bytes(raw)
    (target / "catalogue.json").write_text(json.dumps(manifest, sort_keys=True)+"\n")
    (target / "health.json").write_text(json.dumps({"status": "ok", "mode": "synthetic-only", "cases": 5,
        "uploads": False, "backend": False, "worker_image_id": manifest["worker_image_id"]})+"\n")
    checksums = {str(p.relative_to(target)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(target.rglob("*")) if p.is_file()}
    (output / "artifact-checksums.json").write_text(json.dumps(checksums, indent=2)+"\n")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="Cloud build output; not an application input")
    args = parser.parse_args()
    print(build(args.output))

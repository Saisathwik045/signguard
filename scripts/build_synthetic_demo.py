"""Generate fixed trusted examples, then analyze all of them with the actual Docker worker.

No arbitrary input path/URL is accepted. Fixture generation deliberately runs on trusted
source material, not on uploaded PDFs. No private signing keys are persisted.
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pymupdf

from benchmarks.generate import TEMPLATES, _reveal, base_document, incremental, signature_image
from signguard.container_runner import analyze_container
from signguard.demo import CASES, load_case
from signguard.supervisor import encode_request

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "src/signguard/demo_assets"


def fixtures():
    BUNDLE.mkdir(exist_ok=True)
    signed = TEMPLATES.joinpath("signed-00.pdf").read_bytes()
    checksums = json.loads(TEMPLATES.joinpath("SHA256SUMS.json").read_text())
    assert hashlib.sha256(signed).hexdigest() == checksums["signed-00.pdf"]
    documents = {"genuine_signed": signed, "unsigned": base_document(0)}
    documents["tampered"] = signed.replace(b"%PDF-1.7", b"%PDF-1.6", 1)
    assert documents["tampered"] != signed
    with tempfile.TemporaryDirectory(prefix="sg-trusted-demo-") as directory:
        documents["shadow_modified"] = incremental(signed, Path(directory)/"shadow.pdf", _reveal)
    with pymupdf.open(stream=documents["unsigned"], filetype="pdf") as document:
        document[0].insert_image(pymupdf.Rect(45, 190, 345, 290), stream=signature_image(0))
        documents["visual_only"] = document.tobytes(no_new_id=True, deflate=True)
    for case_id, data in documents.items():
        BUNDLE.joinpath(case_id+".pdf").write_bytes(data)


def analyze(image):
    image_id = subprocess.check_output(["docker", "--host=unix:///var/run/docker.sock", "image", "inspect",
                                       image, "--format", "{{.Id}}"], text=True).strip()
    manifest = {"schema_version": 1, "generated_at": datetime.now(UTC).isoformat(),
                "worker_image_id": image_id, "cases": {}}
    for case_id in CASES:
        data = BUNDLE.joinpath(case_id+".pdf").read_bytes()
        report = analyze_container(encode_request(data), image=image_id)
        raw = (json.dumps(report, indent=2, sort_keys=True)+"\n").encode()
        BUNDLE.joinpath(case_id+".json").write_bytes(raw)
        manifest["cases"][case_id] = {"pdf_sha256": hashlib.sha256(data).hexdigest(),
                                      "report_sha256": hashlib.sha256(raw).hexdigest(),
                                      "source": "Trusted generated synthetic; no private key or user document"}
    BUNDLE.joinpath("manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", help="Regenerate trusted PDF fixtures")
    parser.add_argument("--analyze", action="store_true", help="Analyze fixed bundled PDFs in disposable workers")
    parser.add_argument("--image", default="signguard-worker:phase4", help="Trusted administrator image selection")
    args = parser.parse_args()
    if args.generate:
        fixtures()
    if args.analyze:
        analyze(args.image)
    for case_id in CASES:
        report, _ = load_case(case_id)
        print(case_id, report["structure"]["refined_classification"], report["assessment"]["verdict"])


if __name__ == "__main__":
    main()

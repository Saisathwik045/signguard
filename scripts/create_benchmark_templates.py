"""Explicit corpus-version operation, not run by CI or evaluation."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf

from benchmarks.generate import TEMPLATES, base_document, write_templates

write_templates()
for index in range(10):
    with pymupdf.open(stream=base_document(index), filetype="pdf") as doc:
        data = doc.tobytes(no_new_id=True, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                          owner_pw="synthetic-owner", user_pw="synthetic-user")
    (TEMPLATES / f"encrypted-{index:02d}.pdf").write_bytes(data)
provenance = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(TEMPLATES.glob("*.pdf"))}
(TEMPLATES / "SHA256SUMS.json").write_text(json.dumps(provenance, indent=2, sort_keys=True)+"\n")
print("Saved synthetic public templates; ephemeral signing keys discarded")

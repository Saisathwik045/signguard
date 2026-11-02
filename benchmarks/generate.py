"""Deterministic layouts, fixed seeds and immutable signed public templates.

No detector is imported here. Ground truth comes only from construction operations.
The corpus tests triage alerts, broad document classification and ROI localization.
"""
import hashlib
import json
from io import BytesIO
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw

SEED = 20261102
FAMILIES = (
    "genuine_signed", "tampered_bytes", "appended_content", "shadow_reveal", "shadow_overlay",
    "benign_metadata", "visual_signature", "copied_signature", "unsigned", "negative_rules",
    "negative_logo", "negative_repeated_logos", "faint_signature", "unsigned_forgery", "encrypted",
)
TEMPLATES = Path(__file__).parent / "templates"


def signature_image(index, faint=False, logo=False):
    rng = np.random.default_rng(SEED+index)
    image = Image.new("RGB", (360, 120), "white")
    draw = ImageDraw.Draw(image)
    if logo:
        for n in range(12):
            x = 10+n*27
            draw.rectangle((x, 20, x+18, 90), outline=(0, 0, 0), width=3)
            draw.line((x, 20, x+18, 90), fill=(0, 0, 0), width=2)
    else:
        points = []
        for x in range(12, 346):
            y = 60 + 26*np.sin(x/(7+index%5)) + 12*np.sin(x/3.9) + rng.normal(0, .9)
            points.append((x, int(y)))
        draw.line(points, fill=(215, 215, 215) if faint else (20, 30, 60), width=2)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def base_document(index, hidden=False):
    with pymupdf.open() as doc:
        p = doc.new_page(width=440+index*2, height=340+index*3)
        p.insert_text((30, 35), f"Synthetic contract {index:02d}; amount 100; seed {SEED}")
        if hidden:
            p.insert_text((40, 130), f"HIDDEN amount {900+index}")
            p.draw_rect(pymupdf.Rect(30, 110, 280, 140), color=None, fill=(1, 1, 1), overlay=True)
        return doc.tobytes(no_new_id=True, deflate=True)


def write_templates():
    """One-time provenance operation; save public signed PDFs and discard private keys.

    Templates themselves are immutable corpus inputs. Regenerating them intentionally
    changes their hashes and defines a new benchmark version.
    """
    from tests.fixtures import signed
    TEMPLATES.mkdir(exist_ok=True)
    for index in range(10):
        data, _ = signed(base_document(index, hidden=True))
        (TEMPLATES / f"signed-{index:02d}.pdf").write_bytes(data)
    provenance = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(TEMPLATES.glob("*.pdf"))}
    (TEMPLATES / "SHA256SUMS.json").write_text(json.dumps(provenance, indent=2, sort_keys=True)+"\n")


def incremental(data, output, operation):
    output.write_bytes(data)
    with pymupdf.open(output) as doc:
        operation(doc)
        doc.save(output, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP, no_new_id=True)
    return output.read_bytes()


def _reveal(doc):
    page = doc[0]
    # Remove only the pre-existing opaque cover stream. The hidden text was signed.
    streams = page.get_contents()
    cover = next(x for x in streams if b" re" in doc.xref_stream(x))
    remaining = "["+" ".join(f"{x} 0 R" for x in streams if x != cover)+"]"
    doc.xref_set_key(page.xref, "Contents", remaining)


def _overlay(doc, index):
    p = doc[0]
    p.draw_rect(pymupdf.Rect(25, 18, 420, 42), color=None, fill=(1, 1, 1))
    p.insert_text((30, 35), f"Synthetic contract {index:02d}; amount 99999")


def generate(output, per_family=10):
    if not 1 <= per_family <= 10:
        raise ValueError("per_family must be 1–10")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    checksums = json.loads((TEMPLATES / "SHA256SUMS.json").read_text())
    for name, expected in checksums.items():
        if hashlib.sha256((TEMPLATES / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Immutable template checksum mismatch: {name}")
    manifest = []
    for family in FAMILIES:
        for index in range(per_family):
            case_id = f"{family}-{index:02d}"
            path = output / f"{case_id}.pdf"
            signed = (TEMPLATES / f"signed-{index:02d}.pdf").read_bytes()
            data = base_document(index)
            malicious = family in {"tampered_bytes", "appended_content", "shadow_reveal", "shadow_overlay",
                                   "copied_signature", "unsigned_forgery"}
            supported = family not in {"unsigned_forgery", "encrypted"}
            rois = []
            if family == "genuine_signed":
                data = signed
            elif family == "tampered_bytes":
                data = signed.replace(b"%PDF-1.7", b"%PDF-1.6", 1)
            elif family == "appended_content":
                data = incremental(signed, path, lambda d, i=index: d[0].insert_text((30, 230), f"Changed {i}"))
            elif family == "shadow_reveal":
                data = incremental(signed, path, _reveal)
            elif family == "shadow_overlay":
                data = incremental(signed, path, lambda d, i=index: _overlay(d, i))
            elif family == "benign_metadata":
                data = incremental(signed, path, lambda d, i=index: d.set_metadata({"title": f"Archived {i}"}))
            elif family in {"visual_signature", "copied_signature", "negative_logo",
                            "negative_repeated_logos", "faint_signature", "unsigned_forgery"}:
                with pymupdf.open(stream=data, filetype="pdf") as doc:
                    image = signature_image(index, faint=family == "faint_signature", logo="logo" in family)
                    boxes = [[55, 170, 295, 250]]
                    if family in {"copied_signature", "negative_repeated_logos"}:
                        doc.new_page(width=440+index*2, height=340+index*3)
                        doc[1].insert_text((30, 35), f"Second approval page {index}")
                        boxes.append([75, 200, 315, 280])
                    for number, box in enumerate(boxes):
                        doc[number].insert_image(pymupdf.Rect(box), stream=image)
                        if "logo" not in family:
                            rois.append({"page": number+1, "bbox": box})
                    data = doc.tobytes(no_new_id=True, deflate=True)
            elif family == "negative_rules":
                with pymupdf.open(stream=data, filetype="pdf") as doc:
                    for y in range(90, 280, 20):
                        doc[0].draw_line((30, y), (400, y), width=.7)
                    data = doc.tobytes(no_new_id=True, deflate=True)
            elif family == "encrypted":
                encrypted_template = TEMPLATES / f"encrypted-{index:02d}.pdf"
                if not encrypted_template.exists():
                    raise ValueError("Generate immutable encryption templates first")
                data = encrypted_template.read_bytes()
            path.write_bytes(data)
            expected_class = "cryptographic" if family in FAMILIES[:6] else (
                "visual_candidate" if rois else "unsigned")
            manifest.append({"id": case_id, "path": path.name, "family": family, "malicious": malicious,
                             "supported_alert_evaluation": supported,
                             "unsupported_reason": {"unsigned_forgery": "Single reused signature has no reference or history",
                                                    "encrypted": "Password-protected PDF unsupported"}.get(family),
                             "expected_class": expected_class, "signature_rois": rois,
                             "sha256": hashlib.sha256(data).hexdigest()})
    (output / "manifest.json").write_text(json.dumps({"version": 1, "seed": SEED, "cases": manifest},
                                                   indent=2, sort_keys=True)+"\n")
    return manifest

"""Split-specific synthetic families. Seal the detector before opening holdout outcomes."""
import argparse
import csv
import hashlib
import json
import logging
import resource
import time
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw

from .evaluate import binary_metrics, iou
from .generate import _reveal, incremental

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "benchmarks" / "phase3_templates"
FAMILIES = ("signed", "byte_tamper", "reveal", "overlay", "annotation", "page_replace", "metadata", "visual",
            "copied", "faint", "scan_lowres", "jpeg", "repeated_logo", "stamp", "printed_name", "rotated",
            "multiple", "malformed", "encrypted", "ambiguous_reuse", "table", "scan_printed", "blank", "diagram")
SPLITS = {"development": 310000, "regression": 620000, "holdout": 930000}


def fingerprint():
    return {name: hashlib.sha256((ROOT / "src/signguard" / name).read_bytes()).hexdigest()
            for name in ("images.py", "localization.py", "pdf.py", "pipeline.py")}


def base(split, index):
    seed = SPLITS[split]+index
    with pymupdf.open() as doc:
        page = doc.new_page(width=470+index*7, height=400+index*9)
        page.insert_text((25, 40), f"Approval record {seed}; total 250")
        page.insert_text((25, 125), f"Pre-existing hidden value {seed+900}")
        page.draw_rect(pymupdf.Rect(20, 105, 400, 135), fill=(1, 1, 1), color=None)
        return doc.tobytes(no_new_id=True, deflate=True)


def ink(split, index, kind="signature"):
    rng = np.random.default_rng(SPLITS[split]+index)
    image = Image.new("RGB", (400, 130), "white")
    draw = ImageDraw.Draw(image)
    color = (220+index*3,)*3 if kind == "faint" else (25, 40, 65)
    if kind == "logo":
        # Holdout uses a different primitive; it is not tuned after evaluation.
        for n in range(8):
            box = (8+n*47, 20, 42+n*47, 105)
            if split == "holdout":
                draw.ellipse(box, outline="black", width=3)
            else:
                draw.rectangle(box, outline="black", width=3)
            draw.line((box[0], box[1], box[2], box[3]), fill="black", width=2)
    elif kind == "stamp":
        draw.ellipse((30, 15, 360, 110), outline=(110, 20, 20), width=4)
        draw.text((100, 50), "APPROVED", fill="black", stroke_width=1)
    elif kind == "diagram":
        for x in range(20, 390, 30):
            draw.line((x, 20, x, 110), fill=(210, 210, 210), width=2)
        for y in range(20, 120, 20):
            draw.line((20, y, 380, y), fill=(210, 210, 210), width=2)
    elif split == "development":
        points = [(x, int(65+30*np.sin(x/(9+index))+15*np.sin(x/4))) for x in range(15, 380)]
        draw.line(points, fill=color, width=2)
    elif split == "regression":
        points = [(int(20+t*350+10*np.sin(t*40)), int(65+35*np.sin(t*45))) for t in np.linspace(0, 1, 700)]
        draw.line(points, fill=color, width=2+index%2)
    else:
        previous = (15., 80.)
        for segment in range(6):
            end = (65.+segment*60, float(rng.uniform(40, 95)))
            controls = np.array([previous, (previous[0]+10, rng.uniform(0, 125)),
                                 (end[0]-20, rng.uniform(0, 125)), end])
            points = []
            for t in np.linspace(0, 1, 80):
                xy = (1-t)**3*controls[0]+3*(1-t)**2*t*controls[1]+3*(1-t)*t*t*controls[2]+t**3*controls[3]
                points.append(tuple(xy))
            draw.line(points, fill=color, width=2+index%2)
            previous = end
    return image


def image_bytes(image, quality=None):
    output = BytesIO()
    image.save(output, format="JPEG" if quality else "PNG", **({"quality": quality} if quality else {}))
    return output.getvalue()


def create_templates():
    """Explicit one-time corpus version operation: no private keys persisted."""
    from tests.fixtures import signed
    TEMPLATES.mkdir(exist_ok=True)
    for split in SPLITS:
        for index in range(5):
            data = base(split, index)
            signed_data, _ = signed(data)
            (TEMPLATES / f"{split}-{index}-signed.pdf").write_bytes(signed_data)
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                encrypted = doc.tobytes(no_new_id=True, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                                       user_pw="synthetic", owner_pw="synthetic-owner")
            (TEMPLATES / f"{split}-{index}-encrypted.pdf").write_bytes(encrypted)
    (TEMPLATES / "sha256.json").write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(TEMPLATES.glob("*.pdf"))}, indent=2, sort_keys=True)+"\n")


def generate(output, variants=5):
    output.mkdir(parents=True, exist_ok=True)
    checksums = json.loads((TEMPLATES / "sha256.json").read_text())
    for name, digest in checksums.items():
        assert hashlib.sha256((TEMPLATES / name).read_bytes()).hexdigest() == digest
    cases = []
    for split in SPLITS:
        for family in FAMILIES:
            for index in range(variants):
                case_id = f"{split}-{family}-{index}"
                path = output / (case_id+".pdf")
                signed = (TEMPLATES / f"{split}-{index}-signed.pdf").read_bytes()
                data, rois = base(split, index), []
                if family == "signed":
                    data = signed
                elif family == "byte_tamper":
                    data = signed.replace(b"%PDF-1.7", b"%PDF-1.6", 1)
                elif family == "reveal":
                    data = incremental(signed, path, _reveal)
                elif family in {"overlay", "annotation", "page_replace", "metadata"}:
                    def change(doc, family=family, index=index, split=split):
                        if family == "metadata":
                            doc.set_metadata({"subject": f"Archival {split}-{index}"})
                        elif family == "annotation":
                            annotation = doc[0].add_rect_annot(pymupdf.Rect(20, 15, 430, 55))
                            annotation.set_colors(fill=(1, 1, 1)); annotation.update(opacity=1)
                        elif family == "page_replace":
                            doc.new_page(width=490, height=420)
                            doc[-1].insert_text((25, 40), "Replacement total 99000")
                            doc.delete_page(0)
                        else:
                            doc[0].draw_rect(pymupdf.Rect(20, 15, 430, 55), fill=(1, 1, 1), color=None)
                            doc[0].insert_text((25, 40), "Altered total 99000")
                    data = incremental(signed, path, change)
                elif family == "encrypted":
                    data = (TEMPLATES / f"{split}-{index}-encrypted.pdf").read_bytes()
                elif family == "malformed":
                    data = f"%PDF-1.7\ninvalid-{split}-{index}\n%%EOF\n".encode()
                else:
                    with pymupdf.open(stream=data, filetype="pdf") as doc:
                        if family == "printed_name":
                            doc[0].insert_text((70, 240), "Printed approver: John Example", fontsize=16)
                        elif family == "table":
                            for y in range(170, 350, 20):
                                doc[0].draw_line((20, y), (430, y))
                        elif family != "blank" and family != "scan_printed":
                            kind = {"repeated_logo": "logo", "stamp": "stamp", "faint": "faint",
                                    "diagram": "diagram"}.get(family, "signature")
                            image = ink(split, index, kind)
                            box = [65, 200, 345, 291]
                            doc[0].insert_image(pymupdf.Rect(box), stream=image_bytes(image, 20+index*15 if family == "jpeg" else None))
                            if kind in {"signature", "faint"}:
                                rois.append({"page": 1, "bbox": box})
                            if family in {"copied", "repeated_logo", "multiple"}:
                                doc.new_page(width=470+index*7, height=400+index*9)
                                second = ink(split, index+47) if family == "multiple" else image
                                doc[1].insert_image(pymupdf.Rect(box), stream=image_bytes(second))
                                if family != "repeated_logo":
                                    rois.append({"page": 2, "bbox": box})
                        if family in {"scan_lowres", "scan_printed"}:
                            pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(.65, .65))
                            size = doc[0].rect
                            with pymupdf.open() as scanned:
                                scanned.new_page(width=size.width, height=size.height).insert_image(size, pixmap=pix)
                                data = scanned.tobytes(no_new_id=True, deflate=True)
                        else:
                            if family == "rotated":
                                doc[0].set_rotation(180)
                                rois = [{"page": 1, "bbox": list(pymupdf.Rect(r["bbox"])*doc[0].rotation_matrix)}
                                        for r in rois]
                            data = doc.tobytes(no_new_id=True, deflate=True)
                path.write_bytes(data)
                cases.append({"id": case_id, "split": split, "family": family, "path": path.name,
                              "base_id": f"{split}-{index}", "sha256": hashlib.sha256(data).hexdigest(),
                              "malicious": family in {"byte_tamper", "reveal", "overlay", "annotation", "page_replace",
                                                        "copied", "ambiguous_reuse"},
                              "supported": family not in {"malformed", "encrypted", "ambiguous_reuse"},
                              "expected_class": "cryptographic" if family in FAMILIES[:7] else
                                                "visual_candidate" if rois else "unsigned",
                              "signature_rois": rois})
    # Hash/template leakage across splits is a hard error, including observational duplicates.
    for a in SPLITS:
        for b in SPLITS:
            if a >= b:
                continue
            for key in ("sha256", "base_id"):
                assert not {c[key] for c in cases if c["split"] == a} & {c[key] for c in cases if c["split"] == b}
    (output / "manifest.json").write_text(json.dumps(cases, indent=2, sort_keys=True)+"\n")
    return cases


def summarize(rows):
    supported = [r for r in rows if r["supported"]]
    metrics = binary_metrics([(r["malicious"], r["alert"]) for r in supported])
    metrics["false_positive_rate"] = metrics["fp"]/(metrics["fp"]+metrics["tn"]) if metrics["fp"]+metrics["tn"] else None
    metrics["false_negative_rate"] = metrics["fn"]/(metrics["fn"]+metrics["tp"]) if metrics["fn"]+metrics["tp"] else None
    tp = fp = fn = 0
    for row in rows:
        remaining = list(row["signature_rois"])
        for candidate in row["candidates"]:
            matches = [(iou(candidate["bbox"], roi["bbox"]), n) for n, roi in enumerate(remaining)
                       if candidate["page"] == roi["page"]]
            if matches and max(matches)[0] >= .3:
                remaining.pop(max(matches)[1]); tp += 1
            else:
                fp += 1
        fn += len(remaining)
    classification = defaultdict(Counter)
    for row in rows:
        classification[row["expected_class"]][row["classification"]] += 1
    return {"n": len(rows), "supported_alert": metrics,
            "all_alert": binary_metrics([(r["malicious"], r["alert"]) for r in rows]),
            "localization": {"tp": tp, "fp": fp, "fn": fn,
                             "precision": tp/(tp+fp) if tp+fp else None, "recall": tp/(tp+fn) if tp+fn else None,
                             "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None},
            "classification": {"accuracy": sum(r["classification"] == r["expected_class"] for r in rows)/len(rows),
                               "confusion_matrix": {k: dict(v) for k, v in classification.items()},
                               "per_class": {label: binary_metrics([(r["expected_class"] == label,
                                    r["classification"] == label) for r in rows])
                                    for label in ("cryptographic", "visual_candidate", "unsigned")}},
            "unsupported_rate": sum(not r["supported"] for r in rows)/len(rows),
            "runtime_error_rate": sum("error" in r for r in rows)/len(rows),
            "inconclusive_rate": sum(r.get("verdict") == "inconclusive" for r in rows)/len(rows),
            "unexpected_errors": [r["id"] for r in supported if "error" in r],
            "false_positives": [r["id"] for r in supported if not r["malicious"] and r["alert"]],
            "false_negatives": [r["id"] for r in supported if r["malicious"] and not r["alert"]],
            "seconds": {"total": sum(r["seconds"] for r in rows), "median": float(np.median([r["seconds"] for r in rows])),
                        "p95": float(np.percentile([r["seconds"] for r in rows], 95))},
            "process_high_water_rss_mib": max(r["process_high_water_rss_mib"] for r in rows),
            "memory_limitation": "Cumulative process RSS including native libraries, not isolated per-document peaks"}


def evaluate(output, split):
    from signguard import analyze_pdf
    corpus = output / "pdfs"
    seal = json.loads((output / "seal.json").read_text())
    assert seal["detector"] == fingerprint(), "Detector changed since seal; holdout cannot be called untouched"
    assert seal["manifest_sha256"] == hashlib.sha256((corpus / "manifest.json").read_bytes()).hexdigest()
    rows = []
    for case in json.loads((corpus / "manifest.json").read_text()):
        if case["split"] != split:
            continue
        data = (corpus / case["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == case["sha256"]
        started = time.perf_counter()
        row = {**case, "alert": False, "classification": "unsupported_error", "candidates": []}
        try:
            report = analyze_pdf(data)
            row.update(alert=report["assessment"]["alert"], verdict=report["assessment"]["verdict"],
                       classification=report["structure"]["refined_classification"],
                       candidates=report["image_forensics"]["automatic"]["localization"]["candidates"],
                       findings=[f["code"] for f in report["assessment"]["findings"]])
        except Exception as exc:  # noqa: BLE001 -- all errors remain in outcomes and denominators
            row["error"] = type(exc).__name__
        row.update(seconds=time.perf_counter()-started,
                   process_high_water_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
        rows.append(row)
    (output / f"{split}-outcomes.json").write_text(json.dumps(rows, indent=2, sort_keys=True)+"\n")
    summary = summarize(rows)
    (output / f"{split}-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")
    with (output / f"{split}-outcomes.csv").open("w", newline="") as stream:
        fields = ["id", "family", "malicious", "supported", "alert", "classification", "seconds", "process_high_water_rss_mib"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("phase3-output"))
    parser.add_argument("--create-templates", action="store_true")
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--split", choices=SPLITS)
    parser.add_argument("--variants", type=int, default=5)
    args = parser.parse_args()
    logging.getLogger("pyhanko").setLevel(logging.CRITICAL)
    if args.create_templates:
        create_templates()
    if args.seal:
        if (args.output / "seal.json").exists():
            raise SystemExit("Refusing to overwrite existing seal")
        generate(args.output / "pdfs", args.variants)
        (args.output / "seal.json").write_text(json.dumps({"detector": fingerprint(),
            "manifest_sha256": hashlib.sha256((args.output / "pdfs/manifest.json").read_bytes()).hexdigest(),
            "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2)+"\n")
    if args.split:
        print(json.dumps(evaluate(args.output, args.split), indent=2))


if __name__ == "__main__":
    main()

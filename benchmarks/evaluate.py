"""Evaluate frozen detectors; store every outcome and honest abstention/error counts."""
import argparse
import hashlib
import json
import logging
import platform
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path

from signguard import analyze_pdf

from .generate import SEED, generate


def binary_metrics(rows):
    counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    for truth, prediction in rows:
        counts["tp" if truth and prediction else "fn" if truth else "fp" if prediction else "tn"] += 1
    tp, tn, fp, fn = (counts[key] for key in ("tp", "tn", "fp", "fn"))
    def fraction(a, b):
        return a/b if b else None
    return {**counts, "n": len(rows), "accuracy": fraction(tp+tn, len(rows)),
            "precision": fraction(tp, tp+fp), "recall": fraction(tp, tp+fn),
            "f1": fraction(2*tp, 2*tp+fp+fn),
            "confusion_matrix": [[tn, fp], [fn, tp]], "axes": "rows actual [negative, positive]; columns predicted"}


def iou(a, b):
    area = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-area
    return area/union if union else 0


def evaluate(output, per_family=10):
    output = Path(output)
    manifest = generate(output / "pdfs", per_family)
    outcomes = []
    for case in manifest:
        try:
            report = analyze_pdf((output / "pdfs" / case["path"]).read_bytes())
            outcome = {"id": case["id"], "family": case["family"], "sha256": case["sha256"],
                       "malicious": case["malicious"], "supported": case["supported_alert_evaluation"],
                       "unsupported_reason": case["unsupported_reason"],
                       "expected_class": case["expected_class"],
                       "predicted_class": report["structure"]["classification"],
                       "predicted_alert": report["assessment"]["alert"],
                       "verdict": report["assessment"]["verdict"],
                       "findings": [f["code"] for f in report["assessment"]["findings"]],
                       "analysis_status": report["assessment"]["analysis_status"],
                       "signature_rois": case["signature_rois"],
                       "candidate_boxes": report["image_forensics"]["automatic"]["localization"]["candidates"]}
        except Exception as exc:  # noqa: BLE001 -- evaluation records failures rather than dropping cases
            outcome = {**{k: case[k] for k in ("id", "family", "sha256", "malicious", "expected_class")},
                       "supported": case["supported_alert_evaluation"],
                       "unsupported_reason": case["unsupported_reason"], "predicted_alert": False,
                       "predicted_class": "unsupported_error", "error": f"{type(exc).__name__}: {exc}",
                       "signature_rois": case["signature_rois"], "candidate_boxes": []}
        outcomes.append(outcome)
    supported = [o for o in outcomes if o["supported"]]
    matrix = defaultdict(Counter)
    for outcome in outcomes:
        matrix[outcome["expected_class"]][outcome["predicted_class"]] += 1
    by_family = {}
    for family in sorted({o["family"] for o in outcomes}):
        rows = [o for o in outcomes if o["family"] == family]
        by_family[family] = {"n": len(rows), "alerts": sum(o["predicted_alert"] for o in rows),
                             "errors": sum("error" in o for o in rows), "supported": rows[0]["supported"]}
    # Match each proposal to at most one ground-truth ROI at IoU >= .3.
    loc_tp = loc_fp = loc_fn = 0
    for outcome in outcomes:
        remaining = list(outcome["signature_rois"])
        for candidate in outcome["candidate_boxes"]:
            matches = [(iou(candidate["bbox"], roi["bbox"]), n) for n, roi in enumerate(remaining)
                       if roi["page"] == candidate["page"]]
            if matches and max(matches)[0] >= .3:
                remaining.pop(max(matches)[1])
                loc_tp += 1
            else:
                loc_fp += 1
        loc_fn += len(remaining)
    labels = sorted({o["expected_class"] for o in outcomes})
    classification_metrics = {label: binary_metrics([(o["expected_class"] == label,
                                                     o["predicted_class"] == label) for o in outcomes])
                              for label in labels}
    root = Path(__file__).resolve().parents[1]
    sources = sorted((root / "src" / "signguard").glob("*.py")) + sorted((root / "benchmarks").glob("*.py"))
    summary = {"source_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sources},
               "template_manifest_sha256": hashlib.sha256((root / "benchmarks" / "templates" /
                                                           "SHA256SUMS.json").read_bytes()).hexdigest(),
               "benchmark_version": 1, "seed": SEED, "total": len(outcomes),
               "unique_pdfs": len({o["sha256"] for o in outcomes}),
               "environment": {"python": platform.python_version(), **{name: version(name) for name in
                               ("pyHanko", "PyMuPDF", "opencv-python-headless", "numpy", "Pillow")}},
               "alert_supported": binary_metrics([(o["malicious"], o["predicted_alert"]) for o in supported]),
               "alert_all_cases_including_unsupported": binary_metrics(
                   [(o["malicious"], o["predicted_alert"]) for o in outcomes]),
               "unsupported": [{"id": o["id"], "reason": o["unsupported_reason"], "error": o.get("error")}
                               for o in outcomes if not o["supported"]],
               "unexpected_errors": [{"id": o["id"], "error": o["error"]}
                                     for o in supported if "error" in o],
               "classification": {"accuracy": sum(o["expected_class"] == o["predicted_class"]
                                                  for o in outcomes)/len(outcomes),
                                  "confusion_matrix": {k: dict(v) for k, v in matrix.items()},
                                  "per_class": classification_metrics,
                                  "macro_f1": sum(m["f1"] or 0 for m in classification_metrics.values())/len(labels)},
               "localization": {"iou_threshold": .3, "tp": loc_tp, "fp": loc_fp, "fn": loc_fn,
                                "precision": loc_tp/(loc_tp+loc_fp) if loc_tp+loc_fp else None,
                                "recall": loc_tp/(loc_tp+loc_fn) if loc_tp+loc_fn else None,
                                "f1": 2*loc_tp/(2*loc_tp+loc_fp+loc_fn) if 2*loc_tp+loc_fp+loc_fn else None},
               "false_positives": [o["id"] for o in supported if not o["malicious"] and o["predicted_alert"]],
               "false_negatives": [o["id"] for o in supported if o["malicious"] and not o["predicted_alert"]],
               "by_family": by_family,
               "metric_definition": "Alert=review_required or tampering_detected; inconclusive is no alert, not genuine. "
                                    "Expected unsupported cases excluded from supported metrics, included in all-case metrics. "
                                    "Unexpected errors count as no alert; positives then count as false negatives. "
                                    "Broad classification mistakes are scored on all cases; localization scores all ROIs, including faint ink."}
    output.mkdir(exist_ok=True)
    (output / "outcomes.json").write_text(json.dumps(outcomes, indent=2, sort_keys=True)+"\n")
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("benchmark-output"))
    parser.add_argument("--per-family", type=int, default=10)
    parser.add_argument("--check", action="store_true", help="Fail on unexpected errors or broken integrity families")
    args = parser.parse_args()
    logging.getLogger("pyhanko").setLevel(logging.CRITICAL)
    result = evaluate(args.output, args.per_family)
    print(json.dumps(result, indent=2))
    if args.check:
        critical = ("tampered_bytes", "appended_content", "shadow_reveal", "shadow_overlay", "copied_signature")
        negative_controls = ("genuine_signed", "benign_metadata", "unsigned", "negative_rules", "visual_signature")
        if (result["unexpected_errors"]
                or any(result["by_family"][f]["alerts"] != args.per_family for f in critical)
                or any(result["by_family"][f]["alerts"] for f in negative_controls)):
            raise SystemExit("Benchmark regression: unexpected errors or missed controlled integrity attacks")


if __name__ == "__main__":
    main()

"""Render checked-in measurements; never invent, round-trip or rerun detector labels."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
summary = json.loads((root / "evaluation" / "summary.json").read_text())


def pct(number):
    return f"{number*100:.2f}%" if number is not None else "undefined"


lines = ["# Phase 2 evaluation results", "",
         "Measured in Codex Cloud on 2026-11-02 (Asia/Calcutta). This is a small synthetic",
         "engineering benchmark, not evidence of performance on real signatures or all PDF attacks.", "",
         f"Corpus: **{summary['total']} PDFs, {summary['unique_pdfs']} unique SHA-256 hashes**, 15 families × 10 variants.",
         "Ten visual-signature and unsigned-forgery cases intentionally have identical bytes but different",
         "construction intent. Their ambiguity is reported as unsupported, not removed to improve the score.", "",
         "## Alert evaluation", "",
         "An alert means `review_required` or `tampering_detected`. `inconclusive` means no alert;",
         "it does not mean genuine. Cryptographic byte failures are stronger evidence than a review alert.", "",
         "| Population | N | TP | TN | FP | FN | Accuracy | Precision | Recall | F1 |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
for label, key in [("Supported alert cases", "alert_supported"),
                   ("All cases, including unsupported", "alert_all_cases_including_unsupported")]:
    m = summary[key]
    lines.append(f"| {label} | {m['n']} | {m['tp']} | {m['tn']} | {m['fp']} | {m['fn']} | "
                 f"{pct(m['accuracy'])} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} |")
lines += ["", "Confusion matrices use actual rows `[negative, positive]` and predicted columns `[negative, positive]`.",
          "", "```json", json.dumps({k: summary[k]["confusion_matrix"] for k in
                                       ("alert_supported", "alert_all_cases_including_unsupported")}, indent=2),
          "```", "", "## Outcomes by construction family", "",
          "| Family | PDFs | Alerts | Analysis errors | Included in supported alert metrics |",
          "| --- | ---: | ---: | ---: | --- |"]
for family, m in summary["by_family"].items():
    lines.append(f"| {family} | {m['n']} | {m['alerts']} | {m['errors']} | {m['supported']} |")
lines += ["", f"Unexpected errors among supported cases: **{len(summary['unexpected_errors'])}**.", "",
          "The ten repeated-logo cases are false alerts: geometry can establish repetition but cannot",
          "establish unauthorized copying. There are no supported alert false negatives in this corpus.",
          "Ten single reused signatures without reference/history are unsupported and produce no alert;",
          "they count as false negatives in the all-case matrix. Ten encrypted PDFs raise explicit",
          "unsupported-input errors. Their negative intent and no-alert coding produce all-case TNs,",
          "which must not be mistaken for successful analysis. Supported/all-case scores are both shown.", "",
          "## Broad document classification", "",
          (f"Accuracy: **{pct(summary['classification']['accuracy'])}**; macro F1: "
           f"**{pct(summary['classification']['macro_f1'])}** on all 150 cases."), "",
          "This measures `cryptographic`, `visual_candidate`, and `unsigned`, not forged-vs-genuine identity.",
          "For compatibility with Phase 1, embedded images still produce a broad `visual_candidate` class;",
          "`classification_basis=image_presence_only` distinguishes it from localized non-text ink.",
          "The broad class therefore overcalls logo PDFs, including faint images with no localized ROI.", "",
          "| Class | Precision | Recall | F1 |", "| --- | ---: | ---: | ---: |"]
for label, m in summary["classification"]["per_class"].items():
    lines.append(f"| {label} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} |")
lines += ["", "Classification confusion matrix (actual class → predicted class counts):", "", "```json",
          json.dumps(summary["classification"]["confusion_matrix"], indent=2), "```", "",
          "## Candidate localization", ""]
m = summary["localization"]
lines += [f"One-to-one region matching at IoU ≥ {m['iou_threshold']}: **{m['tp']} TP, {m['fp']} FP, {m['fn']} FN**.",
          f"Precision **{pct(m['precision'])}**, recall **{pct(m['recall'])}**, F1 **{pct(m['f1'])}**.",
          "The ten faint signatures are missed; 30 logo regions are false proposals. These are measured",
          "as errors even though proposals explicitly carry uncertainty. No localization TN is defined",
          "for the effectively infinite set of possible page regions.", "",
          "## Reproduction and provenance", "",
          "In the existing cloud checkout, with dependencies installed:", "", "```sh",
          "python -m benchmarks.evaluate --output benchmark-output --check",
          "pytest -q", "ruff check .", "```", "",
          "Compare `benchmark-output/summary.json` and `outcomes.json` with `evaluation/`. The full manifest",
          "is stored in `evaluation/manifest.json`. PDF hashes, source hashes, template manifest hash and",
          "exact library versions are recorded. `python scripts/render_results.py` regenerates this document",
          "from the checked-in summary. Templates are immutable synthetic public signed/encrypted inputs;",
          "private signing keys were discarded. Do not regenerate templates during reproduction.", "",
          "Within the pinned Python 3.12 environment, two independently generated full corpora were tested",
          "for identical manifests and PDF hashes. Cross-version PDF bytes and detection results are not",
          "guaranteed identical; the Actions matrix runs regression tests and a 30-document smoke corpus.", "",
          "Environment used for the measured full run:", "", "```json", json.dumps(summary["environment"], indent=2),
          "```", "", "## Evaluation limits", "",
          "Variants within a family are correlated, with only ten base signed templates and one synthetic",
          "stroke generator. These are not 150 independent real-world samples. No external dataset, human",
          "handwriting identity evaluation, trained classifier, or untouched third-party holdout is claimed.",
          "Independent regression fixtures use literal PDF syntax, curves, rotations, annotations, restoration",
          "history and transformed texture. They improve correctness coverage but are development tests,",
          "not an unbiased estimate of field accuracy. Thresholds were chosen as conservative geometric",
          "rules before full evaluation; measured logo/faint failures were retained rather than tuned away.",
          "ELA is descriptive only, especially after rendering. ORB does not determine authorization.",
          "Controlled shadow tests cover hidden-content reveal and visual overlay, not every shadow-attack",
          "family, cross-renderer discrepancy, certificate policy, redaction attack or hidden active content.", ""]
(root / "RESULTS.md").write_text("\n".join(lines))

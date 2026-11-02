# Phase 2 evaluation results

Measured in Codex Cloud on 2026-11-02 (Asia/Calcutta). This is a small synthetic
engineering benchmark, not evidence of performance on real signatures or all PDF attacks.

Corpus: **150 PDFs, 140 unique SHA-256 hashes**, 15 families × 10 variants.
Ten visual-signature and unsigned-forgery cases intentionally have identical bytes but different
construction intent. Their ambiguity is reported as unsupported, not removed to improve the score.

## Alert evaluation

An alert means `review_required` or `tampering_detected`. `inconclusive` means no alert;
it does not mean genuine. Cryptographic byte failures are stronger evidence than a review alert.

| Population | N | TP | TN | FP | FN | Accuracy | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Supported alert cases | 130 | 50 | 70 | 10 | 0 | 92.31% | 83.33% | 100.00% | 90.91% |
| All cases, including unsupported | 150 | 50 | 80 | 10 | 10 | 86.67% | 83.33% | 83.33% | 83.33% |

Confusion matrices use actual rows `[negative, positive]` and predicted columns `[negative, positive]`.

```json
{
  "alert_supported": [
    [
      70,
      10
    ],
    [
      0,
      50
    ]
  ],
  "alert_all_cases_including_unsupported": [
    [
      80,
      10
    ],
    [
      10,
      50
    ]
  ]
}
```

## Outcomes by construction family

| Family | PDFs | Alerts | Analysis errors | Included in supported alert metrics |
| --- | ---: | ---: | ---: | --- |
| appended_content | 10 | 10 | 0 | True |
| benign_metadata | 10 | 0 | 0 | True |
| copied_signature | 10 | 10 | 0 | True |
| encrypted | 10 | 0 | 10 | False |
| faint_signature | 10 | 0 | 0 | True |
| genuine_signed | 10 | 0 | 0 | True |
| negative_logo | 10 | 0 | 0 | True |
| negative_repeated_logos | 10 | 10 | 0 | True |
| negative_rules | 10 | 0 | 0 | True |
| shadow_overlay | 10 | 10 | 0 | True |
| shadow_reveal | 10 | 10 | 0 | True |
| tampered_bytes | 10 | 10 | 0 | True |
| unsigned | 10 | 0 | 0 | True |
| unsigned_forgery | 10 | 0 | 0 | False |
| visual_signature | 10 | 0 | 0 | True |

Unexpected errors among supported cases: **0**.

The ten repeated-logo cases are false alerts: geometry can establish repetition but cannot
establish unauthorized copying. There are no supported alert false negatives in this corpus.
Ten single reused signatures without reference/history are unsupported and produce no alert;
they count as false negatives in the all-case matrix. Ten encrypted PDFs raise explicit
unsupported-input errors. Their negative intent and no-alert coding produce all-case TNs,
which must not be mistaken for successful analysis. Supported/all-case scores are both shown.

## Broad document classification

Accuracy: **80.00%**; macro F1: **79.05%** on all 150 cases.

This measures `cryptographic`, `visual_candidate`, and `unsigned`, not forged-vs-genuine identity.
For compatibility with Phase 1, embedded images still produce a broad `visual_candidate` class;
`classification_basis=image_presence_only` distinguishes it from localized non-text ink.
The broad class therefore overcalls logo PDFs, including faint images with no localized ROI.

| Class | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| cryptographic | 100.00% | 100.00% | 100.00% |
| unsigned | 100.00% | 40.00% | 57.14% |
| visual_candidate | 66.67% | 100.00% | 80.00% |

Classification confusion matrix (actual class → predicted class counts):

```json
{
  "cryptographic": {
    "cryptographic": 60
  },
  "unsigned": {
    "unsigned": 20,
    "unsupported_error": 10,
    "visual_candidate": 20
  },
  "visual_candidate": {
    "visual_candidate": 40
  }
}
```

## Candidate localization

One-to-one region matching at IoU ≥ 0.3: **40 TP, 30 FP, 10 FN**.
Precision **57.14%**, recall **80.00%**, F1 **66.67%**.
The ten faint signatures are missed; 30 logo regions are false proposals. These are measured
as errors even though proposals explicitly carry uncertainty. No localization TN is defined
for the effectively infinite set of possible page regions.

## Reproduction and provenance

In the existing cloud checkout, with dependencies installed:

```sh
python -m benchmarks.evaluate --output benchmark-output --check
pytest -q
ruff check .
```

Compare `benchmark-output/summary.json` and `outcomes.json` with `evaluation/`. The full manifest
is stored in `evaluation/manifest.json`. PDF hashes, source hashes, template manifest hash and
exact library versions are recorded. `python scripts/render_results.py` regenerates this document
from the checked-in summary. Templates are immutable synthetic public signed/encrypted inputs;
private signing keys were discarded. Do not regenerate templates during reproduction.

Within the pinned Python 3.12 environment, two independently generated full corpora were tested
for identical manifests and PDF hashes. Cross-version PDF bytes and detection results are not
guaranteed identical; the Actions matrix runs regression tests and a 30-document smoke corpus.

Environment used for the measured full run:

```json
{
  "Pillow": "12.3.0",
  "PyMuPDF": "1.28.2",
  "numpy": "2.5.4",
  "opencv-python-headless": "4.14.0.94",
  "pyHanko": "0.35.2",
  "python": "3.12.14"
}
```

## Evaluation limits

Variants within a family are correlated, with only ten base signed templates and one synthetic
stroke generator. These are not 150 independent real-world samples. No external dataset, human
handwriting identity evaluation, trained classifier, or untouched third-party holdout is claimed.
Independent regression fixtures use literal PDF syntax, curves, rotations, annotations, restoration
history and transformed texture. They improve correctness coverage but are development tests,
not an unbiased estimate of field accuracy. Thresholds were chosen as conservative geometric
rules before full evaluation; measured logo/faint failures were retained rather than tuned away.
ELA is descriptive only, especially after rendering. ORB does not determine authorization.
Controlled shadow tests cover hidden-content reveal and visual overlay, not every shadow-attack
family, cross-renderer discrepancy, certificate policy, redaction attack or hidden active content.

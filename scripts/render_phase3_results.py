"""Export measured Phase 3 evidence and publication artifacts from cloud output directories."""
import argparse
import json
import os
import shutil
import tempfile
import zipfile
from importlib.metadata import version
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "signguard-matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, default=Path("phase3-output"))
parser.add_argument("--legacy", type=Path, default=Path("benchmark-output"))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
destination = root / "evaluation/phase3"
destination.mkdir(exist_ok=True)
for split in ("development", "regression", "holdout"):
    for suffix in ("summary.json", "outcomes.json", "outcomes.csv"):
        shutil.copyfile(args.source / f"{split}-{suffix}", destination / f"{split}-{suffix}")
shutil.copyfile(args.source / "seal.json", destination / "seal.json")
shutil.copyfile(args.source / "pdfs/manifest.json", destination / "manifest.json")
shutil.copyfile(args.legacy / "summary.json", destination / "phase2-replay-summary.json")
shutil.copyfile(args.legacy / "outcomes.json", destination / "phase2-replay-outcomes.json")
# Preserve the sealed bytes across the Pillow security upgrade. Archive contains synthetic inputs only.
with zipfile.ZipFile(destination / "corpus.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(args.source.rglob("*")):
        relative = file.relative_to(args.source)
        if file.is_file() and (relative.parts[0] == "pdfs" or relative.name == "seal.json"):
            info = zipfile.ZipInfo(str(relative), date_time=(2026, 11, 2, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, file.read_bytes())
environment = {name: version(name) for name in ("Pillow", "numpy", "pyHanko", "PyMuPDF", "opencv-python-headless")}
(destination / "environment.json").write_text(json.dumps(environment, indent=2)+"\n")
old = json.loads((root / "evaluation/summary.json").read_text())
replay = json.loads((destination / "phase2-replay-summary.json").read_text())
summaries = {split: json.loads((destination / f"{split}-summary.json").read_text())
             for split in ("development", "regression", "holdout")}


def pct(value):
    return f"{100*value:.2f}%" if value is not None else "undefined"


fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
labels = ["Phase 2", "Phase 3 replay", "Synthetic holdout"]
axes[0].bar(labels, [old["alert_supported"]["accuracy"], replay["alert_supported"]["accuracy"],
                     summaries["holdout"]["supported_alert"]["accuracy"]], color=["#64748b", "#2563eb", "#0d9488"])
axes[0].set(title="Supported triage alert accuracy", ylim=(0, 1.1), ylabel="Fraction")
axes[1].bar(labels, [old["localization"]["f1"], replay["localization"]["f1"], summaries["holdout"]["localization"]["f1"]],
            color=["#64748b", "#2563eb", "#0d9488"])
axes[1].set(title="Candidate localization F1", ylim=(0, 1.1), ylabel="Fraction")
fig.suptitle("Synthetic engineering evaluation; not real-world signature accuracy")
fig.savefig(destination / "comparison.png", dpi=180)
fig.savefig(destination / "comparison.svg")
plt.close(fig)
lines = ["# Phase 3 results", "", "Measured in Codex Cloud on 2026-11-02 (Asia/Calcutta).", "",
         "## Direct replay of unchanged Phase 2 inputs", "",
         "The labels and supported/all-case populations are unchanged. The 150-input replay is a regression",
         "population already inspected during development, not a holdout. Broad classification now uses",
         "the explicitly named `refined_classification`; the legacy image-presence field is retained.", "",
         "| Metric | Phase 2 | Phase 3 replay |", "| --- | ---: | ---: |"]
for label, before, after in [
    ("Supported alert accuracy", old["alert_supported"]["accuracy"], replay["alert_supported"]["accuracy"]),
    ("All-case alert accuracy", old["alert_all_cases_including_unsupported"]["accuracy"], replay["alert_all_cases_including_unsupported"]["accuracy"]),
    ("Broad classification accuracy", old["classification"]["accuracy"], replay["classification"]["accuracy"]),
    ("Localization precision", old["localization"]["precision"], replay["localization"]["precision"]),
    ("Localization recall", old["localization"]["recall"], replay["localization"]["recall"]),
    ("Localization F1", old["localization"]["f1"], replay["localization"]["f1"])]:
    lines.append(f"| {label} | {pct(before)} | {pct(after)} |")
lines += ["", "The ten logo alerts and thirty false proposals from Phase 2 are eliminated on that same corpus;",
          "the ten faint regions are recovered, and all ten controlled copied-signature cases still alert.",
          "Ten single unauthorized-reuse cases remain visually ambiguous and produce no alert. Ten encrypted",
          "PDFs remain unsupported. Unsupported cases were not relabeled or removed.", "",
          "## Expanded split evaluation", "",
          "360 inputs (345 valid synthetic PDFs plus 15 deliberately malformed PDF inputs), three splits",
          "of 120 inputs, 24 families, and five variants per family. Template IDs and PDF hashes are disjoint",
          "across splits. Within-split visual/unauthorized-intent ambiguity is deliberately retained.",
          "Source PDFs/layout IDs differ across splits; generator families and attack concepts are shared.",
          "This is a separate synthetic holdout, not an independent external dataset or field-accuracy estimate.", "",
          "| Split | Supported N | Accuracy | Precision | Recall | F1 | FPR | FNR | All-case accuracy |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
for split, summary in summaries.items():
    m = summary["supported_alert"]
    lines.append(f"| {split} | {m['n']} | {pct(m['accuracy'])} | {pct(m['precision'])} | {pct(m['recall'])} | "
                 f"{pct(m['f1'])} | {pct(m['false_positive_rate'])} | {pct(m['false_negative_rate'])} | "
                 f"{pct(summary['all_alert']['accuracy'])} |")
lines += ["", "| Split | Localization TP/FP/FN | Precision | Recall | F1 | Broad class accuracy | Unsupported | Inconclusive |",
          "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
for split, summary in summaries.items():
    m = summary["localization"]
    lines.append(f"| {split} | {m['tp']}/{m['fp']}/{m['fn']} | {pct(m['precision'])} | {pct(m['recall'])} | "
                 f"{pct(m['f1'])} | {pct(summary['classification']['accuracy'])} | "
                 f"{pct(summary['unsupported_rate'])} | {pct(summary['inconclusive_rate'])} |")
lines += ["", "The holdout has 15 false proposals: five stamps, five scanned printed headers, and five extra",
          "text-like regions on low-resolution scans. These remain counted as false proposals. Supported",
          "alert false positives/negatives are zero in this synthetic holdout, with 30 TP and 75 TN. On all",
          "120 inputs, five ambiguous reuse cases count as FN; ten malformed/encrypted negative-intent cases",
          "error explicitly and are coded no-alert, not successful negative analyses. All-case recall is",
          f"{pct(summaries['holdout']['all_alert']['recall'])}; all-case F1 is {pct(summaries['holdout']['all_alert']['f1'])}.",
          "No unexpected supported-case exceptions occurred. Identity/authorization decisions explicitly abstain.", "",
          "Full binary and broad-class confusion matrices and per-class precision/recall/F1 are in the split",
          "summary JSON. Per-case outcomes, errors, ROI boxes, timings and classifications are in JSON and CSV.", "",
          "## Freeze and security-upgrade chronology", "",
          "The four detector source files were sealed before holdout results were opened; no detector",
          "thresholds or rules were changed after seeing holdout results. The initial holdout ran with",
          "Pillow 12.3.0. Dependency scanning then required Pillow 13.0.0 and pip upgrades. Initial holdout",
          "outcomes are preserved separately, and final results are post-upgrade revalidation of those same",
          "sealed PDF bytes. Revalidation is not another untouched holdout. Corpus ZIP and seal permit exact",
          "input reproduction even if encoding libraries change. No external dataset was acquired.", "",
          "## Timing and memory", "",
          "| Split | Total analysis seconds | Median seconds | P95 seconds | Process high-water RSS MiB |",
          "| --- | ---: | ---: | ---: | ---: |"]
for split, summary in summaries.items():
    m = summary["seconds"]
    lines.append(f"| {split} | {m['total']:.3f} | {m['median']:.4f} | {m['p95']:.4f} | {summary['process_high_water_rss_mib']:.2f} |")
lines += ["", "Timings exclude PDF generation and worker/container cold start. RSS is cumulative process high-water",
          "RSS including native libraries, not isolated per-input peaks. `worker-controls.json` separately",
          "records a disposable worker's measured analysis time and process peak RSS. Values depend on hardware.", "",
          "![Synthetic benchmark comparison](evaluation/phase3/comparison.png)", "",
          "## Cloud reproduction", "", "```sh",
          "python -m pip install -c requirements-cloud.txt -e '.[dev]'",
          "python -m zipfile -e evaluation/phase3/corpus.zip phase3-output",
          "python -m benchmarks.phase3 --output phase3-output --split holdout",
          "pytest -q", "```", "",
          "For a newly generated corpus, choose a new output directory and run `--seal` before any `--split`.",
          "Do not run `--create-templates` during reproduction: it creates new randomized signing/encryption",
          "templates and defines a new corpus version. Public synthetic templates contain no private keys.",
          "Runtime versions are stored in `evaluation/phase3/environment.json`. This evaluation is not a",
          "certificate of safety, comprehensive attack coverage, or evidence of human handwriting identity.", ""]
(root / "RESULTS.md").write_text("\n".join(lines))

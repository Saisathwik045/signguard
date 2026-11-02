"""Corpus integrity and evaluation arithmetic, separate from detector design cases."""
import json

import pytest

from benchmarks.evaluate import binary_metrics
from benchmarks.generate import FAMILIES, generate


def test_metric_arithmetic():
    result = binary_metrics([(True, True)]*3 + [(True, False)] + [(False, True)]*2 + [(False, False)]*4)
    assert result["confusion_matrix"] == [[4, 2], [1, 3]]
    assert result["accuracy"] == .7
    assert result["precision"] == .6
    assert result["recall"] == .75
    assert result["f1"] == pytest.approx(2/3)
    assert binary_metrics([])["accuracy"] is None


def test_full_corpus_determinism_and_coverage(tmp_path):
    first = generate(tmp_path / "a")
    second = generate(tmp_path / "b")
    assert first == second
    assert len(first) == 150
    assert len({case["sha256"] for case in first}) >= 100
    assert {case["family"] for case in first} == set(FAMILIES)
    assert json.loads((tmp_path / "a" / "manifest.json").read_text())["seed"] == 20261102

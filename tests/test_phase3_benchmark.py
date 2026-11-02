"""Split integrity, reproducibility and held-out detector freezing contracts."""
import json

from benchmarks.phase3 import SPLITS, fingerprint, generate


def test_phase3_template_and_hash_separation(tmp_path):
    first = generate(tmp_path / "first", variants=1)
    second = generate(tmp_path / "second", variants=1)
    assert first == second
    assert len(first) == 72
    for a in SPLITS:
        for b in SPLITS:
            if a >= b:
                continue
            assert not {c["base_id"] for c in first if c["split"] == a} & {
                c["base_id"] for c in first if c["split"] == b}
            assert not {c["sha256"] for c in first if c["split"] == a} & {
                c["sha256"] for c in first if c["split"] == b}
    assert len(fingerprint()) == 4
    assert json.loads((tmp_path / "first/manifest.json").read_text()) == first

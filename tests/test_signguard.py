import json
from io import BytesIO
from pathlib import Path

import numpy as np
import pymupdf
import pytest
from PIL import Image

from signguard import analyze_pdf
from signguard.audit import append_event, verify_log
from signguard.images import ela, orb_compare
from signguard.pdf import compare_visual, inspect_pdf
from tests.fixtures import changed_revision, signed, unsigned


@pytest.fixture(scope="module")
def signed_pdf():
    return signed()


def test_unsigned_and_bad_input():
    report = analyze_pdf(unsigned())
    assert report["structure"]["classification"] == "unsigned"
    assert report["assessment"]["verdict"] == "inconclusive"
    for data in [b"garbage", b"%PDF-broken"]:
        with pytest.raises((ValueError, pymupdf.FileDataError)):
            analyze_pdf(data)


def test_signed_integrity_and_explicit_trust(signed_pdf):
    data, cert = signed_pdf
    result = inspect_pdf(data, [cert])
    sig = result["signatures"][0]
    assert result["classification"] == "cryptographic"
    assert sig["intact"] and sig["valid"] and sig["trusted"]
    assert inspect_pdf(data)["signatures"][0]["trusted"] is False


def test_signed_revision_pipeline(signed_pdf):
    report = analyze_pdf(signed_pdf[0], trust_roots=[signed_pdf[1]])
    assert report["visual_comparisons"]
    assert all(p["changed_fraction"] == 0 for p in report["visual_comparisons"][0]["pages"])


def test_incremental_visual_attack(tmp_path, signed_pdf):
    data = changed_revision(signed_pdf[0], tmp_path / "changed.pdf")
    report = analyze_pdf(data)
    assert report["structure"]["revisions"] > inspect_pdf(signed_pdf[0])["revisions"]
    assert report["visual_comparisons"][0]["pages"][0]["changed_fraction"] > 0
    assert report["assessment"]["verdict"] == "review_required"


def test_crypto_content_tampering(signed_pdf):
    # Change a signed header comment without breaking the PDF object graph.
    data = signed_pdf[0].replace(b"%PDF-1.7", b"%PDF-1.6", 1)
    assert data != signed_pdf[0]
    report = analyze_pdf(data)
    assert report["assessment"]["verdict"] == "tampering_detected"


def test_visual_page_changes(tmp_path):
    original = unsigned()
    changed = changed_revision(original, tmp_path / "visual.pdf")
    assert compare_visual(original, original)[0]["changed_fraction"] == 0
    assert compare_visual(original, changed)[0]["changed_fraction"] > 0


def image_bytes(array):
    stream = BytesIO()
    Image.fromarray(array).save(stream, format="PNG")
    return stream.getvalue()


def test_ela_orb():
    noise = image_bytes(np.random.default_rng(4).integers(0, 256, (300, 300, 3), dtype=np.uint8))
    assert ela(noise)["mean_error"] > 0
    assert orb_compare(noise, noise)["inlier_ratio"] > .95
    blank = image_bytes(np.full((50, 50, 3), 255, dtype=np.uint8))
    assert orb_compare(blank, blank)["status"] == "insufficient_features"


def test_audit_mutation_and_truncation(tmp_path):
    path = tmp_path / "audit.jsonl"
    append_event(path, {"a": 1})
    head = append_event(path, {"a": 2})
    assert verify_log(path, head) == (head, 2)
    lines = path.read_text().splitlines(True)
    path.write_text(lines[0])
    with pytest.raises(ValueError, match="head mismatch"):
        verify_log(path, head)
    record = json.loads(lines[0])
    record["event"] = {"a": 99}
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError, match="integrity"):
        verify_log(path)
    with pytest.raises(ValueError):
        append_event(path, {"a": 3})


def test_audited_report(tmp_path):
    path = tmp_path / "audit.jsonl"
    report = analyze_pdf(unsigned(), audit_path=path)
    assert verify_log(path, report["audit_head"])[1] == 1


def test_streamlit_initial_render():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    assert app.button[0].disabled


def test_visual_candidate_classification():
    import pymupdf
    crop = image_bytes(np.full((30, 60, 3), 200, dtype=np.uint8))
    with pymupdf.open(stream=unsigned(), filetype="pdf") as doc:
        doc[0].insert_image(pymupdf.Rect(40, 150, 100, 180), stream=crop)
        assert analyze_pdf(doc.tobytes())["structure"]["classification"] == "visual_candidate"


def test_added_page():
    import pymupdf
    with pymupdf.open(stream=unsigned(), filetype="pdf") as doc:
        doc.new_page(width=400, height=300)
        assert compare_visual(unsigned(), doc.tobytes())[1]["changed_fraction"] == 1


def test_image_forensic_pipeline():
    noise = image_bytes(np.random.default_rng(7).integers(0, 256, (200, 200, 3), dtype=np.uint8))
    report = analyze_pdf(unsigned(), signature_image=noise, reference_image=noise)
    assert report["image_forensics"]["ela"]["mean_error"] > 0
    assert report["image_forensics"]["orb"]["inlier_ratio"] > .95


def test_concurrent_audit_writers(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / "parallel.jsonl"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: append_event(path, {"index": i}), range(20)))
    assert verify_log(path)[1] == 20

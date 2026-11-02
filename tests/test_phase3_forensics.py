import shutil

import pytest

from signguard import analyze_pdf
from signguard.independent import inspect_independently
from signguard.pdf import check_byte_range
from tests.fixtures import signed


def test_every_phase2_failure_regression(tmp_path):
    from benchmarks.generate import generate
    cases = generate(tmp_path)
    families = {"negative_repeated_logos", "negative_logo", "faint_signature", "copied_signature",
                "unsigned_forgery", "encrypted"}
    for case in cases:
        if case["family"] not in families:
            continue
        data = (tmp_path / case["path"]).read_bytes()
        if case["family"] == "encrypted":
            with pytest.raises(ValueError, match="Encrypted"):
                analyze_pdf(data)
            continue
        report = analyze_pdf(data)
        automatic = report["image_forensics"]["automatic"]
        if "logo" in case["family"]:
            assert not report["assessment"]["alert"]
            assert not automatic["localization"]["candidates"]
        elif case["family"] == "faint_signature":
            assert automatic["localization"]["candidates"]
        elif case["family"] == "copied_signature":
            assert report["assessment"]["alert"]
            assert report["assessment"]["verdict"] != "tampering_detected"
        assert report["assessment"]["identity_decision"] == "abstain"


@pytest.mark.parametrize("values", [[0, 10, 5, 4], [0, 10, 20, 1000], [-1, 5, 20, 4],
                                   [0, 10, 20], [0, 10., 20, 4], [0, 10, 20, -4]])
def test_invalid_byte_ranges(values):
    assert not check_byte_range(values, 100)["valid"]


def test_valid_byte_range():
    assert check_byte_range([0, 10, 20, 30], 50)["valid"]


@pytest.mark.skipif(not shutil.which("pdfsig"), reason="Optional independent Poppler tools unavailable")
def test_independent_crypto_and_render_check():
    data, _ = signed()
    result = inspect_independently(data)
    assert result["page_count_agrees"]
    assert result["first_page_normalized_render_mae"] < .05
    assert any("Valid" in value for value in result["signature_validation"])
    altered = data.replace(b"%PDF-1.7", b"%PDF-1.6", 1)
    result = inspect_independently(altered)
    assert any("Mismatch" in value or "Invalid" in value for value in result["signature_validation"])


def test_overlapping_signed_byte_range_is_not_accepted():
    import re
    data, _ = signed()
    match = re.search(rb'/ByteRange\s*\[\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\]', data)
    assert match
    start, end = match.span(3)
    replacement = str(int(match[2])-1).encode().zfill(end-start)
    altered = data[:start]+replacement+data[end:]
    report = analyze_pdf(altered)
    assert not report["structure"]["signatures"][0]["byte_range_check"]["valid"]
    assert report["assessment"]["verdict"] == "tampering_detected"


def test_unsigned_nonvisual_active_content_requires_review(tmp_path):
    import pymupdf

    from tests.fixtures import unsigned
    path = tmp_path / "active.pdf"
    path.write_bytes(unsigned())
    with pymupdf.open(path) as doc:
        doc.xref_set_key(doc.pdf_catalog(), "OpenAction", "<</S/JavaScript/JS(app.alert)>>")
        doc.saveIncr()
    result = analyze_pdf(path.read_bytes())
    assert "ACTIVE_CONTENT_CHANGE" in [f["code"] for f in result["assessment"]["findings"]]

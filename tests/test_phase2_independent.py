"""Held-out construction styles: literal PDF syntax, curves, annotations and transforms.

No benchmark generators or detector thresholds are used to construct these fixtures.
Assertions cover invariants/known attacks, not a claim of real-world accuracy.
"""
from io import BytesIO

import cv2
import numpy as np
import pymupdf
import pytest
from PIL import Image, ImageDraw

from signguard import analyze_pdf
from signguard.images import ela, load_image, orb_compare
from signguard.localization import locate_candidates
from signguard.pdf import analyze_revisions, compare_visual, read_pdf, revision_bytes
from tests.fixtures import signed


def literal_pdf(content):
    """Hand-built one-page PDF independent of the PyMuPDF benchmark writer."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 400] /Resources << /Font << /F1 5 0 R >> >> "
                b"/Contents 4 0 R >>"), b"<< /Length "+str(len(content)).encode()+b" >>\nstream\n"+content+b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    output = b"%PDF-1.7\n"
    offsets = []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output += f"{number} 0 obj\n".encode()+obj+b"\nendobj\n"
    start = len(output)
    output += b"xref\n0 6\n0000000000 65535 f \n"
    output += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    output += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    return output


def png(image):
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def curve_pdf():
    return literal_pdf(b"BT /F1 12 Tf 25 370 Td (Independent approval form) Tj ET\n"
                       b"0.1 0.2 0.5 RG 1.7 w 70 130 m 100 210 100 90 140 160 c "
                       b"180 220 160 85 205 140 c 220 160 240 120 275 150 c S\n")


def test_raw_vector_signature_without_crop():
    report = analyze_pdf(curve_pdf())
    candidates = report["image_forensics"]["automatic"]["localization"]["candidates"]
    assert candidates
    assert any(c["source"] == "nontext_ink" for c in candidates)
    assert all(c["uncertainty"] == "unverified_signature_candidate" for c in candidates)
    assert not report["assessment"]["alert"]


def test_native_table_text_rules_do_not_imply_forgery():
    content = b"BT /F1 10 Tf 30 350 Td (Invoice table and approval text) Tj ET\n"
    for y in range(60, 300, 30):
        content += f".5 w 25 {y} m 450 {y} l S\n".encode()
    report = analyze_pdf(literal_pdf(content))
    assert not report["assessment"]["alert"]
    assert not report["image_forensics"]["automatic"]["localization"]["candidates"]


def test_embedded_fake_eof_is_not_revision_boundary(tmp_path):
    original = literal_pdf(b"% fake %%EOF startxref 7 %%EOF\nBT /F1 12 Tf 25 360 Td (First) Tj ET")
    path = tmp_path / "fake.pdf"
    path.write_bytes(original)
    with pymupdf.open(path) as doc:
        doc[0].insert_text((30, 200), "Second revision")
        doc.saveIncr()
    data = path.read_bytes()
    reader = read_pdf(data)
    assert reader.total_revisions == 2
    assert revision_bytes(data, reader, 0) == original
    assert analyze_revisions(data)[0]["category"] == "visible_content_change"


def test_metadata_allowlist_and_unexplained_changes(tmp_path):
    original, cert = signed(curve_pdf())
    path = tmp_path / "metadata.pdf"
    path.write_bytes(original)
    with pymupdf.open(path) as doc:
        doc.set_metadata({"author": "Archive worker", "subject": "Routine archival metadata"})
        doc.saveIncr()
    report = analyze_pdf(path.read_bytes(), trust_roots=[cert])
    assert report["revision_analysis"][-1]["category"] == "metadata_only"
    assert not report["assessment"]["alert"]
    # A hidden catalog change must not receive metadata-only treatment.
    with pymupdf.open(path) as doc:
        doc.xref_set_key(doc.pdf_catalog(), "PageMode", "/FullScreen")
        doc.saveIncr()
    report = analyze_pdf(path.read_bytes(), trust_roots=[cert])
    assert report["revision_analysis"][-1]["category"] == "nonvisual_structural_change"
    assert report["assessment"]["alert"]


def test_annotation_only_still_requires_review(tmp_path):
    original, cert = signed(curve_pdf())
    path = tmp_path / "annotated.pdf"
    path.write_bytes(original)
    with pymupdf.open(path) as doc:
        annotation = doc[0].add_rect_annot(pymupdf.Rect(55, 180, 300, 290))
        annotation.set_colors(fill=(1, 1, 1), stroke=(1, 1, 1))
        annotation.update(opacity=1)
        doc.saveIncr()
    report = analyze_pdf(path.read_bytes(), trust_roots=[cert])
    assert report["revision_analysis"][-1]["category"] == "annotation_change"
    assert report["assessment"]["alert"]


def test_visual_change_then_restore_retains_history(tmp_path):
    original, cert = signed(curve_pdf())
    path = tmp_path / "restored.pdf"
    path.write_bytes(original)
    with pymupdf.open(path) as doc:
        previous = doc[0].get_contents()
        doc[0].insert_text((30, 200), "Transient malicious content")
        doc.saveIncr()
    with pymupdf.open(path) as doc:
        doc.xref_set_key(doc[0].xref, "Contents", "["+" ".join(f"{x} 0 R" for x in previous)+"]")
        doc.saveIncr()
    report = analyze_pdf(path.read_bytes(), trust_roots=[cert])
    assert report["visual_comparisons"][0]["pages"][0]["changed_fraction"] == 0
    assert any(r["category"] == "visible_content_change" for r in report["revision_analysis"])
    assert report["assessment"]["alert"]


def test_rotation_and_page_deletion_coordinates():
    with pymupdf.open(stream=curve_pdf(), filetype="pdf") as doc:
        doc[0].set_rotation(180)
        doc.new_page(width=500, height=400)
        before = doc.tobytes()
        candidates, _ = locate_candidates(before)
        assert candidates["candidates"]
        for candidate in candidates["candidates"]:
            x0, y0, x1, y1 = candidate["bbox"]
            assert 0 <= x0 < x1 <= 500 and 0 <= y0 < y1 <= 400
        doc.delete_page(1)
        result = compare_visual(before, doc.tobytes())
        assert result[-1]["reason"] == "page added/removed"


def test_transparent_image_composites_on_white():
    image = Image.new("RGBA", (60, 30), (0, 0, 0, 0))
    ImageDraw.Draw(image).line((2, 20, 50, 10), fill=(0, 0, 0, 255), width=2)
    loaded = load_image(png(image))
    assert loaded.getpixel((0, 0)) == (255, 255, 255)


def independent_texture():
    image = np.full((280, 420, 3), 255, dtype=np.uint8)
    rng = np.random.default_rng(987)
    for _ in range(100):
        center = tuple(int(x) for x in rng.integers([15, 15], [400, 260]))
        color = tuple(int(x) for x in rng.integers(0, 180, 3))
        cv2.circle(image, center, int(rng.integers(2, 10)), color, 2)
    return image


def test_orb_transformed_independent_texture():
    image = independent_texture()
    transform = cv2.getRotationMatrix2D((210, 140), 7, .95)
    transformed = cv2.warpAffine(image, transform, (420, 280), borderValue=(255, 255, 255))
    result = orb_compare(png(Image.fromarray(image)), png(Image.fromarray(transformed)))
    assert result["copy_evidence"]
    assert result["geometry_plausible"]


def test_orb_unrelated_and_repetitive_regions():
    a = independent_texture()
    b = np.full_like(a, 255)
    for y in range(10, 270, 20):
        for x in range(10, 410, 20):
            cv2.rectangle(b, (x, y), (x+8, y+8), (0, 0, 0), 1)
    assert not orb_compare(png(Image.fromarray(a)), png(Image.fromarray(b)))["copy_evidence"]


def test_local_matches_cannot_claim_whole_image_copy():
    image = np.full((400, 400, 3), 255, dtype=np.uint8)
    image[20:55, 20:55] = np.random.default_rng(11).integers(0, 256, (35, 35, 3), dtype=np.uint8)
    result = orb_compare(png(Image.fromarray(image)), png(Image.fromarray(image)))
    assert not result["copy_evidence"]


def test_ela_rendered_provenance_never_claims_compression_tampering():
    result = ela(png(Image.fromarray(independent_texture())), provenance="rendered_pdf")
    assert result["status"] == "not_applicable_to_original_compression"
    assert len(result["multi_quality"]) == 3


def test_encrypted_and_revision_budget_are_explicit(tmp_path):
    with pymupdf.open(stream=curve_pdf(), filetype="pdf") as doc:
        encrypted = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="test", owner_pw="owner")
    with pytest.raises(ValueError, match="Encrypted"):
        analyze_pdf(encrypted)
    path = tmp_path / "many.pdf"
    path.write_bytes(curve_pdf())
    for n in range(17):
        with pymupdf.open(path) as doc:
            doc.set_metadata({"title": str(n)})
            doc.saveIncr()
    with pytest.raises(ValueError, match="budget"):
        analyze_pdf(path.read_bytes())


def test_metadata_reference_cannot_allowlist_catalog_changes(tmp_path):
    original, cert = signed(curve_pdf())
    path = tmp_path / "info-catalog.pdf"
    path.write_bytes(original)
    with pymupdf.open(path) as doc:
        catalog = doc.pdf_catalog()
        doc.xref_set_key(catalog, "PageMode", "/FullScreen")
        doc.xref_set_key(-1, "Info", f"{catalog} 0 R")
        doc.saveIncr()
    report = analyze_pdf(path.read_bytes(), trust_roots=[cert])
    assert report["revision_analysis"][-1]["category"] != "metadata_only"
    assert report["assessment"]["alert"]


def test_localization_limit_is_reported_not_silently_complete():
    content = b""
    for y in range(30, 380, 25):
        for x in range(20, 450, 60):
            content += f"1 w {x} {y} m {x+10} {y+15} {x+25} {y-5} {x+38} {y+10} c S\n".encode()
    report = analyze_pdf(literal_pdf(content))
    assert report["image_forensics"]["automatic"]["localization"]["truncated"]
    assert report["assessment"]["analysis_status"] == "partial"
    assert "FORENSIC_BUDGET_REACHED" in report["assessment"]["unsupported_checks"]

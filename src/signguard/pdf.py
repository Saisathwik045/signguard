"""Structural, cryptographic and revision-rendering checks."""
from io import BytesIO

import numpy as np
import pymupdf
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

MAX_BYTES = 25 * 1024 * 1024
MAX_PAGES = 50


def open_pdf(data):
    if not data.startswith(b"%PDF-") or len(data) > MAX_BYTES:
        raise ValueError("Expected a PDF no larger than 25 MiB")
    doc = pymupdf.open(stream=data, filetype="pdf")
    if doc.needs_pass or not 0 < len(doc) <= MAX_PAGES:
        doc.close()
        raise ValueError("Encrypted PDFs and documents outside 1–50 pages are unsupported")
    if any(p.rect.width > 2000 or p.rect.height > 2000 for p in doc):
        doc.close()
        raise ValueError("Page dimensions exceed rendering limits")
    return doc


def inspect_pdf(data, trust_roots=None):
    """Offline verification: trust must be explicitly configured by the caller."""
    with open_pdf(data) as doc:
        images = sum(len(p.get_images()) for p in doc)
    reader = PdfFileReader(BytesIO(data), strict=True)
    signatures = []
    context = ValidationContext(trust_roots=trust_roots or [], allow_fetching=False)
    for sig in reader.embedded_signatures:
        item = {"field": sig.field_name, "signed_revision": sig.signed_revision}
        try:
            status = validate_pdf_signature(sig, signer_validation_context=context)
            item.update(intact=status.intact, valid=status.valid, trusted=status.trusted,
                        coverage=status.coverage.name if status.coverage else None,
                        modification_level=status.modification_level.name if status.modification_level else None,
                        summary=status.summary())
        except Exception as exc:  # noqa: BLE001 -- report per-signature validator failures
            item.update(error=f"{type(exc).__name__}: {exc}", intact=None, valid=None, trusted=False)
        signatures.append(item)
    fields = list(reader.embedded_signatures)
    classification = "cryptographic" if fields else "visual_candidate" if images else "unsigned"
    return {"classification": classification, "embedded_images": images, "signatures": signatures,
            "revisions": reader.total_revisions, "incremental_updates": reader.total_revisions - 1}


def compare_visual(before, after, threshold=16):
    """Render all pages at identical resolution and report pixel changes."""
    results = []
    with open_pdf(before) as old, open_pdf(after) as new:
        for index in range(max(len(old), len(new))):
            if index >= min(len(old), len(new)):
                results.append({"page": index + 1, "changed_fraction": 1.0, "reason": "page added/removed"})
                continue
            a, b = old[index].get_pixmap(), new[index].get_pixmap()
            if (a.width, a.height) != (b.width, b.height):
                fraction = 1.0
            else:
                x = np.frombuffer(a.samples, np.uint8).astype(np.int16)
                y = np.frombuffer(b.samples, np.uint8).astype(np.int16)
                fraction = float(np.mean(np.max(np.abs(x-y).reshape(-1, a.n), axis=1) > threshold))
            results.append({"page": index + 1, "changed_fraction": fraction})
    return results


def signed_revision_comparisons(data):
    reader = PdfFileReader(BytesIO(data), strict=True)
    comparisons = []
    # Let pyHanko validate coverage against the parsed xref chain before slicing.
    seen = set()
    for signature in reader.embedded_signatures:
        revision = signature.signed_revision
        if revision in seen:
            continue
        seen.add(revision)
        coverage = signature.evaluate_signature_coverage().name
        if coverage not in {"ENTIRE_FILE", "ENTIRE_REVISION"}:
            comparisons.append({"signed_revision": revision, "pages": [],
                                "error": "Signature does not cover a complete revision"})
            continue
        end = int(signature.byte_range[2] + signature.byte_range[3])
        comparisons.append({"signed_revision": revision, "pages": compare_visual(data[:end], data)})
    return comparisons

"""Structural, cryptographic and revision-rendering checks."""
import re
from io import BytesIO

import cv2
import numpy as np
import pymupdf
from pyhanko.pdf_utils import generic
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from .input_policy import InputRejected

MAX_BYTES = 25 * 1024 * 1024
MAX_PAGES = 50
MAX_REVISIONS = 16


def read_pdf(data):
    reader = PdfFileReader(BytesIO(data), strict=True)
    if reader.total_revisions > MAX_REVISIONS or len(reader.embedded_signatures) > 12:
        raise InputRejected("revision_limit", "Revision/signature analysis budget exceeded")
    return reader


def open_pdf(data):
    if not data.startswith(b"%PDF-") or len(data) > MAX_BYTES:
        raise InputRejected("invalid_pdf", "Expected a PDF no larger than 25 MiB")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError) as exc:
        raise InputRejected("malformed_pdf", "The PDF cannot be opened safely.") from exc
    if doc.needs_pass:
        doc.close()
        raise InputRejected("encrypted_pdf", "Encrypted PDFs require decryption outside SignGuard; passwords are not accepted.")
    if not 0 < len(doc) <= MAX_PAGES:
        doc.close()
        raise InputRejected("page_limit", "Documents must contain 1–50 pages.")
    if any(p.rect.width > 2000 or p.rect.height > 2000 for p in doc):
        doc.close()
        raise InputRejected("render_limit", "Page dimensions exceed rendering limits")
    return doc


def inspect_pdf(data, trust_roots=None):
    """Offline verification: trust must be explicitly configured by the caller."""
    with open_pdf(data) as doc:
        images = sum(len(p.get_images()) for p in doc)
        page_count = len(doc)
        page_area = sum(p.rect.get_area() for p in doc)
    reader = read_pdf(data)
    if page_count*reader.total_revisions > 160 or page_area*reader.total_revisions > 30_000_000:
        raise InputRejected("render_limit", "Page/revision comparison budget exceeded")
    signatures = []
    context = ValidationContext(trust_roots=trust_roots or [], allow_fetching=False)
    for sig in reader.embedded_signatures:
        item = {"field": sig.field_name, "signed_revision": sig.signed_revision,
                "byte_range_check": check_byte_range(sig.byte_range, len(data)),
                "trust_mode": "offline_explicit_roots", "revocation_state": "not_established_offline"}
        try:
            status = validate_pdf_signature(sig, signer_validation_context=context)
            item.update(intact=status.intact, valid=status.valid, trusted=status.trusted,
                        coverage=status.coverage.name if status.coverage else None,
                        modification_level=status.modification_level.name if status.modification_level else None,
                        summary=status.summary(), trust_state="trusted" if status.trusted else "untrusted_or_unavailable")
        except Exception as exc:  # noqa: BLE001 -- report per-signature validator failures
            item.update(error=f"{type(exc).__name__}: {exc}", intact=None, valid=None, trusted=False,
                        trust_state="validation_error")
        if not item["byte_range_check"]["valid"]:
            item["intact"] = False
        signatures.append(item)
    fields = list(reader.embedded_signatures)
    classification = "cryptographic" if fields else "visual_candidate" if images else "unsigned"
    return {"classification": classification, "embedded_images": images, "signatures": signatures,
            "revisions": reader.total_revisions, "incremental_updates": reader.total_revisions - 1,
            "classification_basis": "embedded_cryptographic_signature" if fields else
                                    "image_presence_only" if images else "no_signature_evidence"}


def compare_visual(before, after, threshold=16):
    """144-DPI comparison, text evidence and annotation-free render attribution."""
    results = []
    with open_pdf(before) as old, open_pdf(after) as new:
        if sum(p.rect.get_area() for doc in (old, new) for p in doc) * 8 > 120_000_000:
            raise ValueError("Comparison rendering budget exceeded")
        for index in range(max(len(old), len(new))):
            if index >= min(len(old), len(new)):
                results.append({"page": index + 1, "changed_fraction": 1.0,
                                "content_changed": True, "text_changed": True,
                                "reason": "page added/removed"})
                continue
            pages = [old[index], new[index]]
            fractions, regions = [], []
            for annotations in (True, False):
                a, b = [p.get_pixmap(matrix=pymupdf.Matrix(2, 2), colorspace=pymupdf.csRGB,
                                    alpha=False, annots=annotations) for p in pages]
                if (a.width, a.height) != (b.width, b.height):
                    fraction = 1.0
                else:
                    x = np.frombuffer(a.samples, np.uint8).astype(np.int16).reshape(a.height, a.width, 3)
                    y = np.frombuffer(b.samples, np.uint8).astype(np.int16).reshape(b.height, b.width, 3)
                    changed = np.max(np.abs(x-y), axis=2) > threshold
                    fraction = float(np.mean(changed))
                    if annotations and fraction:
                        contours, _ = cv2.findContours(changed.astype(np.uint8), cv2.RETR_EXTERNAL,
                                                      cv2.CHAIN_APPROX_SIMPLE)
                        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:32]:
                            rx, ry, rw, rh = cv2.boundingRect(contour)
                            regions.append([rx/2, ry/2, (rx+rw)/2, (ry+rh)/2])
                fractions.append(fraction)
            text_changed = pages[0].get_text("text") != pages[1].get_text("text")
            results.append({"page": index+1, "changed_fraction": fractions[0],
                            "content_changed_fraction": fractions[1],
                            "content_changed": fractions[1] > 0, "text_changed": text_changed,
                            "annotation_only": fractions[0] > 0 and fractions[1] == 0,
                            "changed_regions": regions, "dpi": 144})
    return results


def signed_revision_comparisons(data):
    reader = read_pdf(data)
    comparisons = []
    # Let pyHanko validate coverage against the parsed xref chain before slicing.
    seen = set()
    for signature in reader.embedded_signatures:
        revision = signature.signed_revision
        if revision in seen:
            continue
        seen.add(revision)
        if not check_byte_range(signature.byte_range, len(data))["valid"]:
            comparisons.append({"signed_revision": revision, "pages": [], "error": "Invalid ByteRange"})
            continue
        coverage = signature.evaluate_signature_coverage().name
        if coverage not in {"ENTIRE_FILE", "ENTIRE_REVISION"}:
            comparisons.append({"signed_revision": revision, "pages": [],
                                "error": "Signature does not cover a complete revision"})
            continue
        end = int(signature.byte_range[2] + signature.byte_range[3])
        comparisons.append({"signed_revision": revision, "pages": compare_visual(data[:end], data)})
    return comparisons


def revision_bytes(data, reader, revision):
    """Locate EOF relative to a parsed xref section, verifying its startxref pointer."""
    meta = reader.xrefs.get_xref_container_info(revision)
    start = meta.end_location
    pattern = rb"startxref\s+(\d+)\s+%%EOF(?:\r\n|\r|\n)?"
    for match in re.finditer(pattern, data[start:start+65536]):
        if int(match[1]) == meta.declared_startxref:
            return data[:start+match.end()]
    raise ValueError("Could not establish a revision boundary from xref metadata")


def _metadata_only(reader, revision):
    """Narrow allowlist: only /Info objects and xref containers may change.

    /Root, /Encrypt and page structures must retain their references. XMP or catalog
    changes are intentionally not automatically considered benign.
    """
    previous, current = [reader.trailer.flatten(r) for r in (revision-1, revision)]
    def raw(trailer, key):
        return trailer.raw_get(key) if key in trailer else None
    for key in set(previous) | set(current):
        if (key not in {"/Info", "/ID", "/Prev", "/Size", "/XRefStm"}
                and str(raw(previous, key)) != str(raw(current, key))):
            return False
    allowed = set()
    for rev, trailer in ((revision-1, previous), (revision, current)):
        info = raw(trailer, "/Info")
        if info is not None:
            if not isinstance(info, generic.IndirectObject):
                return False
            value = reader.get_historical_resolver(rev).get_object(info.reference)
            standard = {"/Title", "/Author", "/Subject", "/Keywords", "/Creator", "/Producer",
                        "/CreationDate", "/ModDate", "/Trapped"}
            if not isinstance(value, generic.DictionaryObject) or not set(value).issubset(standard):
                return False
            if any(not isinstance(value.raw_get(key), (generic.TextStringObject, generic.ByteStringObject,
                                                       generic.NameObject)) for key in value):
                return False
            allowed.add((info.idnum, info.generation))
    meta = reader.xrefs.get_xref_container_info(revision)
    if meta.stream_ref is not None:
        allowed.add((meta.stream_ref.idnum, meta.stream_ref.generation))
    changed = reader.xrefs.explicit_refs_in_revision(revision)
    return bool(changed) and not reader.xrefs.refs_freed_in_revision(revision) and all(
        (r.idnum, r.generation) in allowed for r in changed)


def analyze_revisions(data):
    reader = read_pdf(data)
    findings = []
    if reader.total_revisions == 1:
        return findings
    with open_pdf(data) as doc:
        if len(doc)*reader.total_revisions > 160:
            raise InputRejected("render_limit", "Page/revision comparison budget exceeded")
    previous = revision_bytes(data, reader, 0)
    for revision in range(1, reader.total_revisions):
        current = revision_bytes(data, reader, revision)
        pages = compare_visual(previous, current)
        changed = any(p["changed_fraction"] > 0 or p.get("text_changed") for p in pages)
        metadata_only = _metadata_only(reader, revision)
        if metadata_only and not changed:
            category = "metadata_only"
        elif any(p.get("content_changed") or p.get("text_changed") for p in pages):
            category = "visible_content_change"
        elif changed:
            category = "annotation_change"
        else:
            category = "nonvisual_structural_change"
        refs = reader.xrefs.explicit_refs_in_revision(revision)
        if len(refs) > 4096:
            raise ValueError("Modified object budget exceeded")
        active = set()
        types = []
        resolver = reader.get_historical_resolver(revision)
        for ref in sorted(refs, key=lambda r: (r.idnum, r.generation)):
            obj = resolver.get_object(ref)
            if isinstance(obj, generic.DictionaryObject):
                active.update(set(obj) & {"/JS", "/JavaScript", "/OpenAction", "/AA", "/Launch", "/RichMedia"})
                if str(obj.get("/S", "")) in {"/JavaScript", "/Launch"}:
                    active.add(str(obj["/S"]))
                if len(types) < 64:
                    types.append({"object": ref.idnum, "type": str(obj.get("/Type", "untyped"))})
        findings.append({"revision": revision, "category": category, "pages": pages,
                         "modified_object_types": types, "active_content_keys": sorted(active),
                         "changed_objects": len(reader.xrefs.explicit_refs_in_revision(revision)),
                         "freed_objects": len(reader.xrefs.refs_freed_in_revision(revision)),
                         "interpretation": "Narrow metadata-only allowlist" if metadata_only else
                         "Requires signature policy and document context; not proof of attack"})
        previous = current
    return findings


def check_byte_range(values, length):
    valid = (len(values) == 4 and all(isinstance(v, int) and not isinstance(v, bool) for v in values)
             and values[0] == 0 and values[1] > 0 and values[2] > values[1] and values[3] > 0
             and values[2]+values[3] <= length)
    return {"valid": bool(valid), "reason": "ordered_in_bounds" if valid else "malformed_overlapping_or_out_of_bounds",
            "limitation": "CMS Contents gap and revision coverage are checked separately by pyHanko"}

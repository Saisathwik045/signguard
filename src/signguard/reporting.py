"""Bounded evidence and PDF report rendering. This module runs only in the isolated worker."""
import base64
from io import BytesIO

import pymupdf
from PIL import Image, ImageDraw

from .pdf import check_byte_range, open_pdf, read_pdf

MAX_MEDIA = 2*1024*1024


def attach_reports(data, report):
    evidence = []
    media_bytes = 0
    candidates = report["image_forensics"]["automatic"]["localization"]["candidates"]
    changed = [p for c in report["visual_comparisons"] for p in c.get("pages", []) if p["changed_fraction"] > 0]
    selected = sorted({p["page"] for p in changed} | {c["page"] for c in candidates})[:2] or [1]

    def capture(doc, number, label, boxes):
        nonlocal media_bytes
        if number > len(doc):
            return
        page = doc[number-1]
        scale = min(1.5, 900/max(page.rect.width, page.rect.height))
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        draw = ImageDraw.Draw(image)
        for box, color in boxes:
            draw.rectangle([value*scale for value in box], outline=color, width=3)
        output = BytesIO()
        image.save(output, format="PNG")
        value = output.getvalue()
        if media_bytes+len(value) > MAX_MEDIA:
            return
        media_bytes += len(value)
        evidence.append({"page": number, "label": label, "mime": "image/png",
                         "base64": base64.b64encode(value).decode(),
                         "limitations": "Blue: unverified candidate; red: changed region. Rendering is not identity proof."})

    with open_pdf(data) as current:
        for number in selected:
            boxes = [(c["bbox"], "blue") for c in candidates if c["page"] == number]
            boxes += [(b, "red") for p in changed if p["page"] == number for b in p.get("changed_regions", [])]
            capture(current, number, "Current document evidence", boxes)
    if changed and len(evidence) < 3:
        reader = read_pdf(data)
        for sig in reader.embedded_signatures[:1]:
            if check_byte_range(sig.byte_range, len(data))["valid"] and sig.evaluate_signature_coverage().name in {
                    "ENTIRE_FILE", "ENTIRE_REVISION"}:
                end = int(sig.byte_range[2]+sig.byte_range[3])
                with open_pdf(data[:end]) as historical:
                    capture(historical, changed[0]["page"], "Signed revision snapshot", [])
    report["visual_evidence"] = evidence
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        lines = ["SignGuard forensic triage report", "", f"Verdict: {report['assessment']['verdict']}",
                 f"Classification: {report['structure']['refined_classification']}", f"SHA-256: {report['sha256']}",
                 "", "Identity and authorization are not established.", "Audit receipt is supplied separately in JSON.", ""]
        lines += [reason[:180] for reason in report["assessment"]["reasons"][:8]]
        page.insert_textbox(pymupdf.Rect(35, 35, 560, 420), "\n".join(lines), fontsize=10)
        for item in evidence:
            page = document.new_page(width=595, height=842)
            page.insert_text((35, 35), f"{item['label']} - page {item['page']}", fontsize=12)
            page.insert_image(pymupdf.Rect(35, 65, 560, 790), stream=base64.b64decode(item["base64"]))
        pdf = document.tobytes(deflate=True, no_new_id=True)
    report["pdf_report"] = {"mime": "application/pdf", "base64": base64.b64encode(pdf).decode(),
                            "limitations": "Forensic triage only; JSON carries the controller audit receipt"}
    return report

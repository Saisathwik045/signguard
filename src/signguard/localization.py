"""Bounded non-text ink proposals, not a handwriting/authorship classifier."""
from io import BytesIO

import cv2
import numpy as np
import pymupdf
from PIL import Image

from .images import ela, orb_compare
from .pdf import open_pdf

cv2.setNumThreads(1)

MAX_CANDIDATES = 24
SCALE = 1.5


def _png(array):
    output = BytesIO()
    Image.fromarray(array).save(output, format="PNG")
    return output.getvalue()


def graphic_features(mask):
    """Regular repeated components and rectilinear edges are graphic evidence, not identity evidence."""
    _count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    components = [r for r in stats[1:] if r[4] >= 8]
    repeating = False
    if len(components) >= 5:
        sizes = np.asarray([[r[2], r[3]] for r in components], dtype=float)
        repeating = bool(np.max(np.std(sizes, axis=0)/np.maximum(np.mean(sizes, axis=0), 1)) < .25)
    edges = cv2.Canny(mask, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=20, minLineLength=20, maxLineGap=2)
    total = axis = 0.0
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            length = float(np.hypot(x2-x1, y2-y1))
            total += length
            if min(abs(x2-x1), abs(y2-y1)) < .08*max(abs(x2-x1), abs(y2-y1), 1):
                axis += length
    axis_fraction = axis/total if total else 0.0
    return {"components": len(components), "regular_components": repeating,
            "axis_aligned_line_fraction": axis_fraction,
            "graphic_like": bool(repeating or (total > mask.shape[1]*2 and axis_fraction > .8))}


def locate_candidates(data):
    """Return display-coordinate boxes plus ephemeral crop bytes, without storing uploads.

    Native text is masked before grouping non-text ink. Scanned text, logos and diagrams
    may still be proposed; the geometry score is explicitly not a probability.
    """
    candidates, crops, graphics = [], [], []
    truncated = False
    with open_pdf(data) as doc:
        if sum(p.rect.get_area() for p in doc)*SCALE*SCALE > 30_000_000:
            raise ValueError("Localization rendering budget exceeded")
        for number, page in enumerate(doc):
            pix = page.get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE), colorspace=pymupdf.csRGB, alpha=False)
            rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            # Combine absolute ink with locally enhanced low-contrast ink. Noise below 8 levels abstains.
            background = cv2.GaussianBlur(gray, (0, 0), 9)
            contrast = cv2.subtract(background, gray)
            enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
            ink = (((gray < 190) | ((contrast >= 8) & (enhanced < 245))).astype(np.uint8))*255
            for block in page.get_text("blocks"):
                if block[6] != 0:
                    continue
                rect = pymupdf.Rect(block[:4]) * page.rotation_matrix
                x0, y0 = max(0, int(rect.x0*SCALE)-2), max(0, int(rect.y0*SCALE)-2)
                x1, y1 = min(pix.width, int(rect.x1*SCALE)+2), min(pix.height, int(rect.y1*SCALE)+2)
                ink[y0:y1, x0:x1] = 0
            # Two scales close both short disconnected strokes and larger handwriting gaps.
            fine = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 9), np.uint8))
            grouped = cv2.morphologyEx(fine, cv2.MORPH_CLOSE, np.ones((5, 17), np.uint8))
            contours, _ = cv2.findContours(grouped, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            boxes = sorted((cv2.boundingRect(c) for c in contours), key=lambda b: (b[1], b[0]))
            for x, y, width, height in boxes:
                aspect = width / max(height, 1)
                density = float(np.mean(ink[y:y+height, x:x+width] > 0))
                if not (24 <= width <= pix.width*.85 and 8 <= height <= pix.height*.35
                        and 1.3 <= aspect <= 14 and .015 <= density <= .65):
                    continue
                # Reject long rules and solid rectangular marks.
                if height <= 4*SCALE or density > .6:
                    continue
                features = graphic_features(ink[y:y+height, x:x+width])
                if features["graphic_like"]:
                    if len(graphics) < MAX_CANDIDATES:
                        graphics.append({"page": number+1, "bbox": [v/SCALE for v in (x, y, x+width, y+height)],
                                         "features": features, "decision": "likely_regular_graphic",
                                         "uncertainty": "Heuristic rejection; handwriting can also be regular"})
                    continue
                if len(candidates) == MAX_CANDIDATES:
                    truncated = True
                    break
                x0, y0 = max(0, x-6), max(0, y-6)
                x1, y1 = min(pix.width, x+width+6), min(pix.height, y+height+6)
                bbox = [round(v/SCALE, 2) for v in (x0, y0, x1, y1)]
                intersects_image = any((pymupdf.Rect(block[:4]) * page.rotation_matrix).intersects(
                    pymupdf.Rect(bbox)) for block in page.get_text("blocks") if block[6] == 1)
                candidates.append({"id": f"p{number+1}-c{len(candidates)+1}", "page": number+1,
                                   "bbox": bbox, "coordinate_space": "rotated_page_points",
                                   "source": "raster_ink" if intersects_image else "nontext_ink",
                                   "uncertainty": "unverified_signature_candidate",
                                   "ink_density": round(density, 4), "features": features,
                                   "contrast_method": "absolute_and_local_multiscale",
                                   "limitations": ["May be a logo, diagram, scanned text or decoration",
                                                   "Not evidence of authorship or forgery"]})
                crops.append(_png(rgb[y0:y1, x0:x1]))
            if truncated:
                break
    return {"status": "candidates_found" if candidates else "no_candidates",
            "candidates": candidates, "truncated": truncated, "graphics": graphics,
            "abstention": "No confident handwriting identity decision is available",
            "limitations": ["Native text is excluded; signatures encoded as text may be missed",
                            "Small, faint, vertical or connected-to-text signatures may be missed"]}, crops


def automatic_forensics(data, reference=None):
    localization, crops = locate_candidates(data)
    evidence = []
    for candidate, crop in zip(localization["candidates"], crops, strict=True):
        item = {"candidate_id": candidate["id"], "ela": ela(crop, provenance="rendered_pdf")}
        if reference is not None:
            item["reference_match"] = orb_compare(crop, reference)
        evidence.append(item)
    copies = []
    # Bound comparisons; deterministic order, no exhaustive quadratic workload.
    pair_count = 0
    for left in range(len(crops)):
        for right in range(left+1, len(crops)):
            if pair_count == 100:
                break
            pair_count += 1
            match = orb_compare(crops[left], crops[right])
            if match.get("copy_evidence"):
                copies.append({"candidate_ids": [localization["candidates"][left]["id"],
                                                  localization["candidates"][right]["id"]],
                               "match": match, "interpretation": "Repeated visual region; authorization unknown"})
    return {"localization": localization, "candidates": evidence, "copy_candidates": copies,
            "pairs_checked": pair_count, "pair_limit_reached": len(crops)*(len(crops)-1)//2 > pair_count}

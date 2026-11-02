"""ELA and ORB are forensic indicators, never proof of forgery."""
from io import BytesIO
from threading import Lock

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageOps, ImageStat

_RANSAC_LOCK = Lock()

def load_image(data):
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > 16_000_000:
            raise ValueError("Image exceeds 16 megapixels")
        image = ImageOps.exif_transpose(image).convert("RGBA")
        white = Image.new("RGBA", image.size, "white")
        return Image.alpha_composite(white, image).convert("RGB")


def ela(data, quality=90, provenance="uploaded_image"):
    image = load_image(data)
    scores = []
    difference = None
    for level in sorted({quality, 80, 95}):
        output = BytesIO()
        image.save(output, format="JPEG", quality=level)
        difference = ImageChops.difference(image, load_image(output.getvalue()))
        gray = np.asarray(difference.convert("L"), dtype=np.float32)
        tiles = [float(np.mean(gray[y:y+32, x:x+32]))
                 for y in range(0, gray.shape[0], 32) for x in range(0, gray.shape[1], 32)]
        median = float(np.median(tiles))
        mad = float(np.median(np.abs(np.asarray(tiles)-median)))
        scores.append({"quality": level, "mean_error": float(np.mean(gray)),
                       "tile_median": median, "tile_mad": mad,
                       "max_tile_error": max(tiles)})
        if level == quality:
            stats = ImageStat.Stat(difference)
            mean_error = float(np.mean(stats.mean))
            max_error = max(v[1] for v in difference.getextrema())
    return {"mean_error": mean_error, "max_error": max_error, "quality": quality,
            "multi_quality": scores, "provenance": provenance,
            "status": "not_applicable_to_original_compression" if provenance == "rendered_pdf" else "descriptive_only",
            "interpretation": "Residuals are descriptive, not a forgery score; rendering destroys compression history"}


def orb_compare(candidate, reference):
    a = cv2.cvtColor(np.array(load_image(candidate)), cv2.COLOR_RGB2GRAY)
    b = cv2.cvtColor(np.array(load_image(reference)), cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(nfeatures=1500, edgeThreshold=10, fastThreshold=10)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None or min(len(ka), len(kb)) < 4:
        return {"status": "insufficient_features", "good_matches": 0, "inlier_ratio": None,
                "copy_evidence": False}
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    def unique_matches(first, second):
        pairs = matcher.knnMatch(first, second, k=2)
        return {p[0].queryIdx: p[0] for p in pairs
                if len(p) == 2 and p[0].distance < 0.7*p[1].distance and p[0].distance <= 48}

    forward, backward = unique_matches(da, db), unique_matches(db, da)
    good = [m for m in forward.values()
            if m.trainIdx in backward and backward[m.trainIdx].trainIdx == m.queryIdx]
    ratio, inliers, coverage, geometry = None, 0, 0.0, False
    if len(good) >= 4:
        src = np.float32([ka[m.queryIdx].pt for m in good])
        dst = np.float32([kb[m.trainIdx].pt for m in good])
        with _RANSAC_LOCK:
            cv2.setRNGSeed(0)
            transform, mask = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
        if mask is not None and transform is not None and np.isfinite(transform).all():
            selected = mask.ravel().astype(bool)
            inliers, ratio = int(selected.sum()), float(selected.mean())
            if inliers >= 4:
                area_a = cv2.contourArea(cv2.convexHull(src[selected])) / a.size
                area_b = cv2.contourArea(cv2.convexHull(dst[selected])) / b.size
                coverage = float(min(area_a, area_b))
                corners = np.float32([[0, 0], [a.shape[1], 0], [a.shape[1], a.shape[0]],
                                      [0, a.shape[0]]]).reshape(-1, 1, 2)
                projected = cv2.perspectiveTransform(corners, transform)
                scale = abs(cv2.contourArea(projected)) / a.size
                geometry = bool(cv2.isContourConvex(projected) and .1 < scale < 10
                                and np.linalg.cond(transform) < 1e6)
    evidence = inliers >= 12 and ratio >= .65 and coverage >= .08 and geometry
    return {"status": "compared", "good_matches": len(good), "inlier_ratio": ratio,
            "inliers": inliers, "spatial_coverage": coverage, "geometry_plausible": geometry,
            "copy_evidence": bool(evidence),
            "candidate_keypoints": len(ka), "reference_keypoints": len(kb),
            "limitations": ["Similar regions may be legitimately reused", "Low-texture handwriting may be unsupported",
                            "Strong rotation, cropping, scaling or recompression can cause missed matches"]}

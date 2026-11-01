"""ELA and ORB are forensic indicators, never proof of forgery."""
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageStat


def load_image(data):
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > 16_000_000:
            raise ValueError("Image exceeds 16 megapixels")
        return image.convert("RGB")


def ela(data, quality=90):
    image = load_image(data)
    output = BytesIO()
    image.save(output, format="JPEG", quality=quality)
    recompressed = load_image(output.getvalue())
    difference = ImageChops.difference(image, recompressed)
    stats = ImageStat.Stat(difference)
    return {"mean_error": float(np.mean(stats.mean)), "max_error": max(v[1] for v in difference.getextrema()),
            "quality": quality, "interpretation": "Compression residual only; no calibrated forgery probability"}


def orb_compare(candidate, reference):
    a = cv2.cvtColor(np.array(load_image(candidate)), cv2.COLOR_RGB2GRAY)
    b = cv2.cvtColor(np.array(load_image(reference)), cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(nfeatures=1500)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None or min(len(ka), len(kb)) < 4:
        return {"status": "insufficient_features", "good_matches": 0, "inlier_ratio": None}
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    ratio = None
    if len(good) >= 4:
        src = np.float32([ka[m.queryIdx].pt for m in good])
        dst = np.float32([kb[m.trainIdx].pt for m in good])
        _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        if mask is not None:
            ratio = float(mask.mean())
    return {"status": "compared", "good_matches": len(good), "inlier_ratio": ratio,
            "candidate_keypoints": len(ka), "reference_keypoints": len(kb)}

"""Optional bounded Poppler cross-check; independent of pyHanko and MuPDF, not a trust oracle."""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from .pdf import open_pdf


def inspect_independently(data):
    required = ("pdfinfo", "pdftoppm", "pdfsig")
    if not all(shutil.which(name) for name in required):
        return {"status": "unsupported", "reason": "Poppler tools unavailable"}
    with open_pdf(data) as doc, tempfile.TemporaryDirectory(prefix="signguard-poppler-") as directory:
        if len(doc) > 5:
            return {"status": "unsupported", "reason": "Cross-check limited to five pages"}
        path = Path(directory)/"input.pdf"
        path.write_bytes(data)
        info = subprocess.run(["pdfinfo", str(path)], capture_output=True, timeout=10, check=True).stdout.decode()
        match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
        count = int(match[1]) if match else None
        subprocess.run(["pdftoppm", "-f", "1", "-singlefile", "-scale-to", "1000", "-png", str(path),
                        str(Path(directory)/"render")], capture_output=True, timeout=10, check=True)
        with Image.open(Path(directory)/"render.png") as image:
            image = image.convert("RGB")
            pix = doc[0].get_pixmap()
            baseline = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).resize(image.size)
            delta = float(np.mean(np.abs(np.asarray(image).astype(float)-np.asarray(baseline).astype(float)))/255)
        sig = subprocess.run(["pdfsig", "-nocert", "-no-ocsp", str(path)], capture_output=True,
                             timeout=10, check=False).stdout.decode(errors="replace")
        mupdf_pages = len(doc)
        validations = re.findall(r"Signature Validation:\s*([^\r\n]+)", sig)
    return {"status": "completed", "page_count_agrees": count == mupdf_pages,
            "first_page_normalized_render_mae": delta, "signature_validation": validations,
            "trust_validation": "disabled", "limitation": "Diagnostic first-page render; neither renderer is ground truth"}

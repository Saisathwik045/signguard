"""Package the read-only dashboard from an explicit public-synthetic file allowlist."""
import argparse
import json
import zipfile
from pathlib import Path

from signguard.demo import CASES, load_downloads

ROOT = Path(__file__).resolve().parents[1]


def package(target):
    assets = {
        "synthetic_demo.py": (ROOT / "synthetic_demo.py").read_bytes(),
        "signguard/__init__.py": b"",
        "signguard/demo.py": (ROOT / "src/signguard/demo.py").read_bytes(),
        "signguard/dashboard.py": (ROOT / "src/signguard/dashboard.py").read_bytes(),
        "signguard/dashboard_assets/evaluation.json": (ROOT / "src/signguard/dashboard_assets/evaluation.json").read_bytes(),
        "signguard/demo_assets/manifest.json": (ROOT / "src/signguard/demo_assets/manifest.json").read_bytes(),
        "requirements.txt": (ROOT / "deploy/requirements-demo.txt").read_bytes(),
        ".streamlit/config.toml": (ROOT / "deploy/dashboard.streamlit.toml").read_bytes(),
        ".gitignore": b".venv/\n__pycache__/\n*.py[cod]\n.streamlit/secrets.toml\n.env\n.DS_Store\n",
        ".gitattributes": b"*.pdf binary\n",
        "README.md": (ROOT / "DASHBOARD_GUIDE.md").read_bytes(),
    }
    manifest = json.loads(assets["signguard/demo_assets/manifest.json"])
    if set(manifest["cases"]) != set(CASES):
        raise ValueError("Unexpected synthetic catalogue")
    for case in CASES:
        document, report = load_downloads(case)
        assets[f"signguard/demo_assets/{case}.pdf"] = document
        assets[f"signguard/demo_assets/{case}.json"] = report
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(assets.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 21, 0, 0, 0))
            archive.writestr(info, value, compress_type=zipfile.ZIP_DEFLATED)
    return {"archive": str(target), "files": len(assets), "cases": list(CASES), "live_uploads": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(package(parser.parse_args().output), indent=2))

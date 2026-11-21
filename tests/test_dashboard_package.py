"""The distributable cannot acquire worker authority or silently alter snapshots."""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

from scripts.package_dashboard import package


def test_minimal_package_runs_all_pages_without_parser_imports(tmp_path):
    archive = tmp_path / "demo.zip"
    result = package(archive)
    assert result["live_uploads"] is False
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert not any(name.endswith(("worker.py", "client.py", "pipeline.py", "executor.py")) for name in names)
        assert not any(name.startswith(".github/") for name in names)
        manifest = json.loads(bundle.read("signguard/demo_assets/manifest.json"))
        for case, entry in manifest["cases"].items():
            for suffix, key in ((".pdf", "pdf_sha256"), (".json", "report_sha256")):
                assert hashlib.sha256(bundle.read("signguard/demo_assets/"+case+suffix)).hexdigest() == entry[key]
        folder = tmp_path / "extracted"
        bundle.extractall(folder)
    program = '''
import pathlib, sys
sys.path.insert(0, str(pathlib.Path.cwd()))
from streamlit.testing.v1 import AppTest
from signguard.dashboard import PAGES
import signguard.dashboard
assert pathlib.Path(signguard.dashboard.__file__).resolve() == pathlib.Path('signguard/dashboard.py').resolve()
app = AppTest.from_file('synthetic_demo.py').run()
for page in PAGES:
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception
    assert not app.get('file_uploader')
assert not any(name in sys.modules for name in ('pyhanko', 'pymupdf', 'cv2', 'signguard.client', 'signguard.worker'))
'''
    subprocess.run([sys.executable, "-B", "-c", program], cwd=folder, check=True, capture_output=True, timeout=40)


def test_packaging_is_reproducible(tmp_path):
    first, second = tmp_path / "a.zip", tmp_path / "b.zip"
    package(first)
    package(second)
    assert first.read_bytes() == second.read_bytes()
    assert Path(first).stat().st_size > 0

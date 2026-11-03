import json

from scripts.build_private_viewer import build
from signguard.demo import CASES, load_case


def test_static_artifact_has_only_allowlisted_assets(tmp_path):
    root = build(tmp_path)
    expected = {"index.html", "styles.css", "app.js", "catalogue.json", "health.json"}
    expected |= {f"reports/{case_id}.json" for case_id in CASES}
    assert {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} == expected
    assert not list(root.rglob("*.py"))
    for case_id in CASES:
        assert json.loads((root / "reports" / (case_id+".json")).read_text()) == load_case(case_id)[0]
    health = json.loads((root / "health.json").read_text())
    assert health["cases"] == 5 and not health["uploads"] and not health["backend"]

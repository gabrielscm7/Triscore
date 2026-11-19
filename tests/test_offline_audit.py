from __future__ import annotations

from pathlib import Path

from app.services.offline_audit import scan_external_references

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def test_templates_css_js_and_svg_have_no_external_references():
    findings = scan_external_references(APP_DIR)
    assert findings == [], "\n".join(
        f"{item.path}:{item.line} {item.value}" for item in findings
    )

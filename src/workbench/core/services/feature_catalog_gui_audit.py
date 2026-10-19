"""Conservative source-template coverage triage for the operator Feature Catalog.

Template markers are curated. Presence does not prove runtime behavior or complete coverage.
"""
from pathlib import Path
from workbench.core.services.feature_catalog import ROOT, load_catalog

SAMPLES = (
    ("Binary Inspector", "gui/templates/binary_inspector.html", (
        ("Feature probe sets", "binary-probe-sets"),
        ("Protocol Compatibility", "binary-protocol-evidence"),
        ("Running client version (memory scan)", "binary-running-version"),
        ("Sections", "binary-pe-inspection"),
        ("Diff", "binary-compare"),
    )),
    ("Retail Version Explorer", "gui/templates/retail_versions.html", (
        ('tab == "manifest"', "retail-manifest"),
        ('tab == "planner"', "retail-download-plan"),
        ('tab == "artifacts"', "retail-artifacts"),
        ('tab == "compare"', "retail-compare"),
    )),
    ("Assault Tracker", "gui/templates/domain_assault.html", (
        ("Mission readiness and next actions", "assault"),
        ("System-wide and shared dependencies", "assault"),
    )),
)

def audit_gui_controls(root: Path = ROOT) -> dict:
    features = {f["id"] for f in load_catalog(root / "feature_catalog/features.json")}
    pages = []
    for module, relative_path, controls in SAMPLES:
        path = root / relative_path
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        rows = [{"marker": marker, "feature_id": feature_id,
                 "template_present": marker in text,
                 "catalog_present": feature_id in features}
                for marker, feature_id in controls]
        pages.append({"module": module, "template": relative_path, "controls": rows})
    missing = [{"module": page["module"], **row}
               for page in pages for row in page["controls"]
               if not row["template_present"] or not row["catalog_present"]]
    return {"pages": pages, "missing": missing, "sample_count": sum(len(p["controls"]) for p in pages),
            "note": "Static curated control samples only. Template and catalog presence do not establish complete tab, handler, help, or live-test coverage."}

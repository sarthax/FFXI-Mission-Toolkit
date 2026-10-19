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
    ("Auction House", "gui/templates/auction_house.html", (
        ("Economy health", "ah-economy"),
        ("Administrative action preview", "ah-restock"),
        ("Item detail", "ah-browse"),
    )),
    ("Auction House Cleanup", "gui/templates/auction_house_cleanup.html", (
        ("Target rules", "ah-restock"),
        ("Last action", "ah-restock"),
    )),
    ("Auction House Reward History", "gui/templates/auction_house_reward_history.html", (
        ("Interrupted delivery attempts", "ah-recovery"),
        ("DSP MyISAM recovery cases", "ah-recovery"),
    )),
    ("Live Client Bridge", "gui/templates/live_client_bridge.html", (
        ("Install Ashita addon locally", "live-bridge"),
        ("Headless client observation", "live-bridge"),
        ("Nearby observed entities", "live-entity-stream"),
    )),
    ("Wiki", "gui/templates/wiki.html", (
        ("tab == 'browse'", "wiki-cache"),
        ("tab == 'translation'", "wiki-translation"),
        ("/wiki/cache-health", "wiki-cache"),
        ("/wiki/scrape", "wiki-bulk"),
    )),
    ("Feature Testing", "gui/templates/feature_testing.html", (
        ("ft-design-preset", "testing-scenario-builder"),
        ("ft-observation-guide", "testing-scenario-builder"),
        ("Run history", "testing-run-inspector"),
        ("/feature-testing/run/", "testing-run-inspector"),
    )),
    ("Feature Trace", "gui/templates/feature_trace.html", (
        ("Wiki evidence path", "trace-wiki-provenance"),
        ("Open exact Wiki source", "trace-wiki-provenance"),
    )),
    ("Wiki source navigation", "gui/templates/wiki.html", (
        ("data-focus-section", "wiki-source-navigation"),
        ("wiki-focused-source-section", "wiki-source-navigation"),
    )),
    ("Captures", "gui/templates/captures.html", (
        ("/captures/search", "capture-search"),
        ("/captures/bulk-ingest", "capture-bulk-ingest"),
        ("/captures/metadata-import", "capture-metadata-import"),
        ("/captures/review", "capture-review"),
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

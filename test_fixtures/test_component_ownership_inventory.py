import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "workbench" / "COMPONENT_OWNERSHIP.json"
FINAL_NAMESPACE_OWNERS = {
    "src/workbench/captures/": "captures",
    "src/workbench/validation/": "validation_packages",
    "src/workbench/packages/": "validation_packages",
    "src/workbench/devtools/": "devtools",
    "src/workbench/editors/": "editors",
}


def _manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _owner_for_src(path: Path, manifest: dict):
    rel = path.relative_to(ROOT).as_posix()
    explicit = manifest["explicit_src_overrides"]
    if rel in explicit:
        return explicit[rel]

    if path.name == "__init__.py":
        # Namespace/package markers inherit their containing package and do not
        # represent an independently deployable product implementation.
        return "namespace"

    if rel == "src/workbench/gui_shell.py":
        return "bootstrap_tests"

    for prefix, owner in FINAL_NAMESPACE_OWNERS.items():
        if rel.startswith(prefix):
            return owner

    for rule in manifest["path_rules"]:
        if rel.startswith(rule["prefix"]):
            return rule["owner"]
    return None


def test_root_python_ownership_map_is_exact():
    manifest = _manifest()
    mapped = manifest["root_python_files"]
    actual = {p.name for p in ROOT.glob("*.py")}

    assert len(mapped) == 97
    assert set(mapped) == actual
    assert set(mapped.values()) <= set(manifest["owners"])


def test_all_src_workbench_python_has_an_owner():
    manifest = _manifest()
    src_root = ROOT / "src" / "workbench"
    unowned = []
    for path in sorted(src_root.rglob("*.py")):
        if _owner_for_src(path, manifest) is None:
            unowned.append(path.relative_to(ROOT).as_posix())
    assert not unowned, f"Unowned src/workbench Python modules: {unowned}"


def test_final_component_namespaces_have_expected_owners():
    manifest = _manifest()
    for rel, expected in {
        "src/workbench/devtools/entities/profile_graph.py": "devtools",
        "src/workbench/devtools/features/checker.py": "devtools",
        "src/workbench/devtools/features/trace_catalog.py": "devtools",
        "src/workbench/devtools/features/trace_providers.py": "devtools",
    }.items():
        path = ROOT / rel
        assert path.exists(), rel
        assert _owner_for_src(path, manifest) == expected


def test_known_core_services_product_code_is_explicitly_reclassified():
    manifest = _manifest()
    overrides = manifest["explicit_src_overrides"]

    expected_non_core = {
        "src/workbench/core/services/capture_integrity.py": "captures",
        "src/workbench/core/services/pcap_ingest.py": "captures",
        "src/workbench/core/services/feature_checker.py": "devtools",
        "src/workbench/core/services/feature_trace_catalog.py": "devtools",
        "src/workbench/core/services/client_binary_graph.py": "client_shared",
        "src/workbench/core/services/feature_package_analyzer.py": "validation_packages",
        "src/workbench/core/services/id_bridge.py": "validation_packages",
    }
    for path, owner in expected_non_core.items():
        assert overrides[path] == owner


def test_split_review_is_small_and_explicit():
    manifest = _manifest()
    assert set(manifest["needs_split_review"]) == {
        "src/workbench/core/services/capability_producers.py",
        "src/workbench/core/services/identity_resolver.py",
    }

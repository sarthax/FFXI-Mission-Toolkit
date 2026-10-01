import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "workbench"

# Final product namespaces. Legacy modules inventoried elsewhere are migrated in
# Phase C; this test prevents new violations inside the final component homes.
PREFIX_OWNER = {
    "core": "core",
    "runtime": "core",
    "client": "client_shared",
    "captures": "captures",
    "validation": "validation_packages",
    "packages": "validation_packages",
    "devtools": "devtools",
    "editors": "editors",
}

ALLOWED = {
    "core": {"core"},
    "client_shared": {"core", "client_shared"},
    "captures": {"core", "client_shared", "captures", "devtools"},
    "validation_packages": {"core", "client_shared", "captures", "devtools", "validation_packages"},
    "devtools": {"core", "client_shared", "captures", "devtools"},
    "editors": {"core", "client_shared", "devtools", "editors"},
}


def _module_owner(module: str):
    if not module.startswith("workbench."):
        return None
    part = module.split(".", 2)[1]
    return PREFIX_OWNER.get(part)


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_final_component_namespaces_obey_dependency_direction():
    violations = []
    for top_level, owner in PREFIX_OWNER.items():
        base = SRC / top_level
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            # core/services remains an explicitly inventoried legacy mixing area
            # until Phase C; enforce final shared Core files but not that folder.
            if top_level == "core" and "services" in path.relative_to(base).parts:
                continue
            for imported in _imports(path):
                target = _module_owner(imported)
                if target and target not in ALLOWED[owner]:
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()}: {owner} -> {target} via {imported}"
                    )
    assert not violations, "Forbidden component imports:\n" + "\n".join(violations)


def test_core_contracts_do_not_import_product_components():
    contracts = SRC / "core" / "contracts"
    for path in contracts.rglob("*.py"):
        for imported in _imports(path):
            target = _module_owner(imported)
            assert target in {None, "core"}, f"Core contract imports product component: {imported}"


def test_component_namespace_imports_are_isolated():
    cases = {
        "workbench.captures": {"workbench.validation", "workbench.packages", "workbench.editors", "workbench.devtools"},
        "workbench.validation": {"workbench.captures", "workbench.editors", "workbench.devtools"},
        "workbench.packages": {"workbench.captures", "workbench.editors", "workbench.devtools"},
        "workbench.devtools": {"workbench.validation", "workbench.packages", "workbench.editors"},
        "workbench.editors": {"workbench.validation", "workbench.packages", "workbench.captures"},
    }
    for module, forbidden in cases.items():
        script = (
            "import importlib,sys; "
            f"importlib.import_module({module!r}); "
            f"bad=[m for m in {sorted(forbidden)!r} if m in sys.modules]; "
            "assert not bad, bad"
        )
        subprocess.run([sys.executable, "-c", script], cwd=ROOT, check=True)

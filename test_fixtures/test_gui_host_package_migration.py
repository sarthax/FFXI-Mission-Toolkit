from __future__ import annotations

from pathlib import Path


def test_root_gui_server_is_launcher_only():
    root = Path("gui_server.py").read_text(encoding="utf-8")
    assert "from workbench.app import host as _canonical" in root
    assert "_canonical.main()" in root
    assert "sys.modules[__name__] = _canonical" in root
    assert "@app." not in root
    assert "FastAPI(" not in root


def test_packaged_host_loader_preserves_repo_path_and_canonical_uvicorn_target():
    loader = Path("src/workbench/app/host.py").read_text(encoding="utf-8")
    assert 'REPO_ROOT / "gui_server.py"' in loader
    assert '_LOADER_FILE.with_name("_host_impl.py")' in loader
    assert "compile(_IMPL_FILE.read_text" in loader
    assert 'uvicorn.run("workbench.app.host:app"' in loader


def test_gui_host_implementation_is_owned_under_src():
    impl = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    assert 'app = FastAPI(title="Mission Toolkit GUI")' in impl
    assert '@app.get("/captures/search"' in impl
    assert '@app.get("/researchgaps"' in impl
    assert '@app.get("/domains"' in impl
    assert 'if __name__ == "__main__":' in impl

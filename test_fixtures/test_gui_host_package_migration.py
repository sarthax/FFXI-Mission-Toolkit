from __future__ import annotations

from pathlib import Path


def test_root_gui_server_launcher_is_retired():
    assert not Path("gui_server.py").exists()

def test_packaged_host_loader_uses_packaged_impl_and_canonical_uvicorn_target():
    loader = Path("src/workbench/app/host.py").read_text(encoding="utf-8")
    assert '_LOADER_FILE.with_name("_host_impl.py")' in loader
    assert 'REPO_ROOT / "gui_server.py"' not in loader
    assert "compile(_IMPL_FILE.read_text" in loader
    assert 'uvicorn.run("workbench.app.host:app"' in loader


def test_gui_host_implementation_is_owned_under_src():
    impl = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    assert 'app = FastAPI(title="Mission Toolkit GUI")' in impl
    assert '@app.get("/captures/search"' in impl
    assert '@app.get("/researchgaps"' in impl
    assert '@app.get("/domains"' in impl
    assert 'if __name__ == "__main__":' in impl

"""Ensure the host exposes Live Client read-only replay endpoints."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_host_registration_is_explicit_and_read_only():
    host = (ROOT / "src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    assert "live_client_replay_registry = ReplayRegistry()" in host
    assert "app.include_router(create_registry_router(live_client_replay_registry))" in host
    assert "app.include_router(create_replay_console_router())" in host

    from fastapi import FastAPI
    from workbench.runtime.live_client.registry import ReplayRegistry
    from workbench.runtime.live_client.registry_api import create_registry_router
    from workbench.runtime.live_client.replay_console import create_replay_console_router

    app = FastAPI()
    app.include_router(create_registry_router(ReplayRegistry()))
    app.include_router(create_replay_console_router())
    paths = app.openapi()["paths"]
    assert set(paths["/live-client/replay/clients"]) == {"get"}
    assert set(paths["/live-client/replay/projection"]) == {"get"}
    assert set(paths["/live-client/replay/console"]) == {"get"}

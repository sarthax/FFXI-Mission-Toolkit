"""Real-browser recording controls against an isolated offline HTTP server."""
import json
import socket
import threading
import time

import pytest
from fastapi import FastAPI
import uvicorn

from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.registry_api import create_registry_router
from workbench.runtime.live_client.replay_console import create_replay_console_router
from workbench.runtime.live_client.setup_api import create_recording_upload_router


def test_recording_controls_in_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    registry = ReplayRegistry()
    app = FastAPI()
    app.include_router(create_registry_router(registry))
    app.include_router(create_replay_console_router())
    app.include_router(create_recording_upload_router(tmp_path, registry))
    sock = socket.socket(); sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline, 'server failed to start'
            time.sleep(.01)
        frames = [{'schema_version': 1, 'client_id': 'same-client', 'client_version': 'fixture',
                   'character': 'Hero', 'adapter': 'offline', 'observed_at': i,
                   'position': {'zone_id': 101 if i == 2 else 100, 'x': i, 'y': 0, 'z': 2*i, 'heading': 0},
                   'entities': []} for i in range(1, 5)]
        content = ''.join(json.dumps(f) + '\n' for f in frames).encode()
        with playwright.sync_playwright() as p:
            import os
            browser = p.chromium.launch(executable_path=os.environ.get('LIVE_CLIENT_CHROMIUM'), headless=True)
            page = browser.new_page()
            errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}/live-client/replay/console')
            page.locator('#recording').set_input_files({'name': 'walk.jsonl', 'mimeType': 'application/x-ndjson', 'buffer': content})
            page.locator('#open-recording').click()
            playwright.expect(page.locator('#state')).to_have_text('Frame 1 of 4')
            first = page.locator('#client').input_value()
            page.locator('#open-recording').click()
            playwright.expect(page.locator('#client option')).to_have_count(3)
            page.wait_for_function('(first)=>document.getElementById("client").value!==first', arg=first)
            second = page.locator('#client').input_value()
            assert first != second
            page.locator('#compare').select_option(first)
            playwright.expect(page.locator('#comparison')).to_contain_text('Comparison: Hero')
            page.locator('#timeline').evaluate('(el)=>{el.value="3";el.dispatchEvent(new Event("change",{bubbles:true}));}')
            playwright.expect(page.locator('#state')).to_have_text('Frame 3 of 4')
            playwright.expect(page.locator('#trace polyline')).to_have_count(2)
            assert registry._clients[first].position == 1
            page.locator('#restart').click()
            playwright.expect(page.locator('#state')).to_have_text('Frame 1 of 4')
            page.locator('#play').click()
            playwright.expect(page.locator('#play')).to_have_text('Pause')
            page.locator('#play').click()
            page.wait_for_timeout(1100)
            assert registry._clients[second].position == 1
            page.locator('#speed').select_option('4')
            page.locator('#play').click()
            playwright.expect(page.locator('#state')).to_have_text('Frame 4 of 4')
            playwright.expect(page.locator('#play')).to_have_text('Play')
            page.locator('#replace').click()
            playwright.expect(page.locator('#state')).to_have_text('Frame 1 of 4')
            assert page.locator('#client').input_value() == second
            page.locator('#unload').click()
            playwright.expect(page.locator('#client option')).to_have_count(2)
            assert registry.client_ids() == (first,)
            assert not errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()

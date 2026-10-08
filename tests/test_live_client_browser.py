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
from workbench.runtime.live_client.waypoint_library import WaypointLibrary
from workbench.runtime.live_client.waypoint_library_api import create_waypoint_library_router


def test_recording_controls_in_browser(tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    registry = ReplayRegistry()
    app = FastAPI()
    app.include_router(create_registry_router(registry))
    from pathlib import Path
    from fastapi.templating import Jinja2Templates
    from workbench.gui_shell import build_shell_context
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / 'gui' / 'templates'))
    templates.env.globals.update(current_theme=lambda: 'dark', backport_enabled=lambda: False)
    templates.env.globals['shell_context'] = lambda request: build_shell_context(
        path=request.url.path, method=request.method, settings={},
        default_topaz_root='/missing', default_backport_root='/missing')
    def render(request, style, body):
        return templates.TemplateResponse(request, 'live_client_console.html',
                                          {'console_style': style, 'console_body': body})
    app.include_router(create_replay_console_router(render))
    app.include_router(create_recording_upload_router(tmp_path, registry))
    library = WaypointLibrary(tmp_path / 'waypoint-library.db')
    app.include_router(create_waypoint_library_router(library, registry))
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
                   'observation_scope': 'bounded_loaded_entities', 'entities_truncated': True,
                   'entities': []} for i in range(1, 5)]
        content = ''.join(json.dumps(f) + '\n' for f in frames).encode()
        with playwright.sync_playwright() as p:
            import os
            browser = p.chromium.launch(executable_path=os.environ.get('LIVE_CLIENT_CHROMIUM'), headless=True)
            page = browser.new_page()
            errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}/live-client/replay/console')
            playwright.expect(page.locator('#app-shell')).to_be_visible()
            page.locator('#recording').set_input_files({'name': 'walk.jsonl', 'mimeType': 'application/x-ndjson', 'buffer': content})
            page.locator('#open-recording').click()
            playwright.expect(page.locator('#state')).to_have_text('Frame 1 of 4')
            playwright.expect(page.locator('#entity-status')).to_contain_text('truncated.')
            playwright.expect(page.locator('#entity-status')).to_contain_text('up to 32')
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

            # Real Ashita data varies substantially in X/Y; X/Z alone hides
            # most recorded travel. Exercise all planes in the shared shell.
            capture = Path(__file__).parent / 'fixtures/live_client/ashita_v4_runtime_anonymized.jsonl'
            page.locator('#recording').set_input_files(str(capture))
            page.locator('#open-recording').click()
            playwright.expect(page.locator('#state')).to_have_text('Frame 1 of 121')
            runtime_session = page.locator('#client').input_value()
            playwright.expect(page.locator('#trace-plane')).to_have_value('xy')
            playwright.expect(page.locator('#source')).to_have_text('ashita-v4-api-experimental')
            playwright.expect(page.locator('#version')).to_have_text('unverified-ashita-v4-api')
            page.locator('#timeline').evaluate('(el)=>{el.value="121";el.dispatchEvent(new Event("change",{bubbles:true}));}')
            playwright.expect(page.locator('#trace-status')).to_contain_text('121 observed positions')
            playwright.expect(page.locator('#trace polyline')).to_have_count(1)
            page.locator('#waypoint-name').fill('Runtime stairs')
            with page.expect_download() as pending:
                page.locator('#capture-player').click()
            downloaded = json.loads(Path(pending.value.path()).read_text())
            assert downloaded['waypoints'][0]['name'] == 'Runtime stairs'
            assert downloaded['waypoints'][0]['position']['zone_id'] == 50
            assert downloaded['provenance']['session_id'] == runtime_session
            assert downloaded['provenance']['version_verified'] is False
            page.locator('#save-player').click()
            playwright.expect(page.locator('#waypoint-rows tr')).to_have_count(1)
            saved, = library.entries()
            assert saved['position'] == downloaded['waypoints'][0]['position']
            assert saved['provenance'] == downloaded['provenance']
            page.locator('#waypoint-rows input').fill('Renamed runtime landing')
            page.locator('#waypoint-rows').get_by_role('button', name='Rename', exact=True).click()
            playwright.expect(page.locator('#waypoint-rows input')).to_have_value('Renamed runtime landing')
            page.reload()
            playwright.expect(page.locator('#waypoint-rows input')).to_have_value('Renamed runtime landing')
            page.locator('#client').select_option(runtime_session)
            playwright.expect(page.locator('#state')).to_have_text('Frame 121 of 121')
            page.locator('#waypoint-name').fill('Runtime target')
            with page.expect_download() as pending:
                page.locator('#export-path').click()
            path_document = json.loads(Path(pending.value.path()).read_text())
            assert len(path_document['samples']) == 121
            assert path_document['samples'][-1]['position'] == downloaded['waypoints'][0]['position']
            def displayed_span():
                return page.locator('#trace polyline').evaluate('''el => {
                    const pairs=el.getAttribute('points').split(' ').map(p=>p.split(',').map(Number));
                    return [0,1].map(i=>Math.max(...pairs.map(p=>p[i]))-Math.min(...pairs.map(p=>p[i])));
                }''')
            xy = displayed_span()
            assert xy[0] > 200 and xy[1] > 200
            for plane, label in [('xz', 'X/Z'), ('yz', 'Y/Z')]:
                page.locator('#trace-plane').select_option(plane)
                playwright.expect(page.locator('#trace-status')).to_contain_text('relative '+label)
                span = displayed_span()
                assert span[0] > 500 and span[1] < 40
            assert registry._clients[runtime_session].position == 121
            page.locator('#client').select_option(first)
            playwright.expect(page.locator('#trace-plane')).to_have_value('xz')
            page.locator('#client').select_option(runtime_session)
            playwright.expect(page.locator('#trace-plane')).to_have_value('yz')
            page.locator('#restart').click()
            playwright.expect(page.locator('#trace-status')).to_contain_text('1 observed positions')
            playwright.expect(page.locator('#trace-plane')).to_have_value('yz')
            # Inspect an actual target-bearing frame and ensure target details
            # disappear on a frame with no observed target.
            capture_frames = [json.loads(line) for line in capture.read_text().splitlines()]
            target_frame = next(i for i, f in enumerate(capture_frames, 1) if f['entities'])
            target = capture_frames[target_frame-1]['entities'][0]
            page.locator('#timeline').evaluate('(el,n)=>{el.value=String(n);el.dispatchEvent(new Event("change",{bubbles:true}));}', target_frame)
            playwright.expect(page.locator('#entity-rows tr')).to_have_count(1)
            playwright.expect(page.locator('#entity-rows td').nth(0)).to_have_text(target['name'])
            playwright.expect(page.locator('#entity-rows td').nth(3)).to_have_text('Unknown')
            with page.expect_download() as pending:
                page.locator('#entity-rows').get_by_role('button', name='Download waypoint', exact=True).click()
            target_document = json.loads(Path(pending.value.path()).read_text())
            assert target_document['waypoints'][0]['position'] == target['position']
            assert target_document['observation']['server_entity_id'] is None
            page.locator('#entity-rows').get_by_role('button', name='Save to library', exact=True).click()
            playwright.expect(page.locator('#waypoint-rows tr')).to_have_count(2)
            assert library.entries()[-1]['position'] == target['position']
            page.locator('#waypoint-search').fill('LANDING')
            page.locator('#filter-waypoints').click()
            playwright.expect(page.locator('#waypoint-rows tr')).to_have_count(1)
            page.locator('#waypoint-zone').fill('51'); page.locator('#filter-waypoints').click()
            playwright.expect(page.locator('#waypoint-rows tr')).to_have_count(0)
            page.locator('#waypoint-zone').fill('50'); page.locator('#filter-waypoints').click()
            playwright.expect(page.locator('#waypoint-rows tr')).to_have_count(1)
            with page.expect_download() as pending:
                page.locator('#download-library').click()
            library_document = json.loads(Path(pending.value.path()).read_text())
            assert len(library_document['waypoints']) == 2
            page.locator('#waypoint-rows').get_by_role('button', name='Delete', exact=True).click()
            playwright.expect(page.locator('#waypoint-rows tr')).to_have_count(0)
            page.locator('#waypoint-search').fill(''); page.locator('#filter-waypoints').click()
            playwright.expect(page.locator('#waypoint-rows tr')).to_have_count(1)
            page.locator('#waypoint-file').set_input_files({'name': 'library.json', 'mimeType': 'application/json',
                'buffer': json.dumps(library_document).encode()})
            page.locator('#import-waypoints').click()
            playwright.expect(page.locator('#waypoint-rows tr')).to_have_count(3)
            assert len(library.entries()) == 3
            # Stored waypoints are meaningful in their original recording visit,
            # with raw differences and markers independent of native game writes.
            playwright.expect(page.locator('#relative-waypoint option')).to_have_count(4)
            chosen = library.entries()[0]['id']
            page.locator('#relative-waypoint').select_option(chosen)
            playwright.expect(page.locator('#relative-status')).to_contain_text('Straight-line distance')
            page.locator('#show-waypoints').check()
            playwright.expect(page.locator('#trace .waypoint-marker')).to_have_count(3)
            playwright.expect(page.locator('#trace .waypoint-delta')).to_have_count(1)
            assert registry._clients[runtime_session].position == target_frame
            page.locator('#trace-plane').select_option('xy')
            playwright.expect(page.locator('#trace .waypoint-marker')).to_have_count(3)
            page.locator('#client').select_option(first)
            playwright.expect(page.locator('#relative-waypoint option')).to_have_count(1)
            playwright.expect(page.locator('#trace .waypoint-marker')).to_have_count(0)
            page.locator('#client').select_option(runtime_session)
            playwright.expect(page.locator('#trace .waypoint-marker')).to_have_count(3)
            playwright.expect(page.locator('#relative-waypoint')).to_have_value(chosen)
            page.locator('#show-waypoints').uncheck()
            playwright.expect(page.locator('#trace .waypoint-marker')).to_have_count(0)
            empty_frame = next(i for i, f in enumerate(capture_frames, 1) if not f['entities'])
            page.locator('#timeline').evaluate('(el,n)=>{el.value=String(n);el.dispatchEvent(new Event("change",{bubbles:true}));}', empty_frame)
            playwright.expect(page.locator('#entity-rows tr')).to_have_count(0)
            playwright.expect(page.locator('#entity-status')).to_have_text('No entity observations in this frame.')
            # Exercise bounded inventory inspection without altering playback.
            inventory = {**frames[0], 'client_id': 'inventory-ui',
                         'position': {'zone_id': 100, 'x': 1e308, 'y': 0, 'z': 0},
                         'entities': [
                {'client_index': 12, 'server_entity_id': 123, 'name': '<img src=x onerror=alert(1)>', 'position': {'zone_id': 100, 'x': -1e308, 'y': 0, 'z': 0}},
                {'client_index': 11, 'name': 'Same name', 'position': {'zone_id': 100, 'x': 1e308, 'y': 6, 'z': 8}},
                {'client_index': 10, 'server_entity_id': 16780001, 'name': 'Same name', 'position': {'zone_id': 100, 'x': 1e308, 'y': 3, 'z': 4}},
            ]}
            page.locator('#recording').set_input_files({'name': 'inventory.jsonl', 'mimeType': 'application/x-ndjson', 'buffer': (json.dumps(inventory)+'\n').encode()})
            page.locator('#open-recording').click()
            playwright.expect(page.locator('#entity-rows tr')).to_have_count(3)
            playwright.expect(page.locator('#entity-status')).to_contain_text('truncated.')
            assert page.locator('#entity-rows img').count() == 0
            inspection_session = page.locator('#client').input_value()
            page.locator('#entity-sort').select_option('distance')
            playwright.expect(page.locator('#entity-rows tr').nth(0).locator('td').nth(2)).to_have_text('10')
            playwright.expect(page.locator('#entity-rows tr').nth(0).locator('td').nth(5)).to_have_text('5.000 raw')
            playwright.expect(page.locator('#entity-rows tr').nth(2).locator('td').nth(5)).to_have_text('Outside numeric range')
            page.locator('#entity-search').fill('SAME NAME')
            playwright.expect(page.locator('#entity-rows tr')).to_have_count(2)
            page.locator('#entity-search').fill('0x'+format(16780001, 'x'))
            playwright.expect(page.locator('#entity-rows tr')).to_have_count(1)
            playwright.expect(page.locator('#entity-rows td').nth(2)).to_have_text('10')
            page.locator('#entity-search').fill('0xB')
            playwright.expect(page.locator('#entity-rows td').nth(2)).to_have_text('11')
            page.locator('#entity-search').fill('no match')
            playwright.expect(page.locator('#entity-rows tr')).to_have_count(0)
            playwright.expect(page.locator('#entity-status')).to_contain_text('0 of 3')
            playwright.expect(page.locator('#entity-status')).to_contain_text('truncated.')
            page.locator('#entity-search').fill('')
            playwright.expect(page.locator('#entity-rows tr')).to_have_count(3)
            assert registry._clients[inspection_session].position == 1
            assert not errors
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()

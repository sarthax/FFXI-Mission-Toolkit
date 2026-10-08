"""Same-origin toolkit library actions; never invoke a writable client adapter."""
import json
import sqlite3

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from .observation_exports import capture_waypoint, recording_context
from .waypoint_library import MAX_DOCUMENT_BYTES, WaypointLibrary
from .waypoint_comparison import compare_waypoints
from .observation_guard import require_observation


def create_waypoint_library_router(library: WaypointLibrary, registry) -> APIRouter:
    router = APIRouter(prefix='/live-client/waypoints', tags=['Live Client Waypoint Library'])

    def authorize(request):
        if request.headers.get('origin') != str(request.base_url).rstrip('/'):
            raise HTTPException(403, 'same-origin request required')

    def operation(function):
        try:
            return function()
        except KeyError as exc:
            raise HTTPException(404, exc.args[0]) from exc
        except (ValueError, TypeError, RecursionError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except (OSError, sqlite3.Error) as exc:
            raise HTTPException(503, 'waypoint library storage unavailable; existing data preserved') from exc

    @router.get('')
    def entries(search: str = Query(default='', max_length=200),
                zone_id: int | None = Query(default=None, ge=0, le=65535)):
        return {'waypoints': operation(lambda: library.entries(search=search, zone_id=zone_id))}

    @router.get('/export')
    def export():
        return JSONResponse(operation(library.export_document), headers={
            'Content-Disposition': 'attachment; filename="waypoint-library.json"', 'Cache-Control': 'no-store'})

    @router.get('/relative')
    def relative(client_id: str = Query(min_length=1, max_length=200),
                 observed_at: float | None = Query(default=None)):
        if client_id not in registry.client_ids():
            raise HTTPException(404, 'observation session not registered')
        frame = registry.frame(client_id)
        if frame is None:
            raise HTTPException(409, 'session has no observed frame')
        if observed_at is not None and observed_at != frame.snapshot.observed_at:
            raise HTTPException(409, 'observation changed; refresh waypoint comparison')
        return operation(lambda: compare_waypoints(frame, client_id, library.entries(),
                                                    recording_context(registry, client_id, frame)))

    @router.post('/capture')
    def capture(request: Request, client_id: str = Query(min_length=1, max_length=200),
                name: str = Query(min_length=1, max_length=200),
                entity_index: int | None = Query(default=None, ge=0, le=65535),
                observation_token: str | None = Query(default=None, min_length=64, max_length=64)):
        authorize(request)
        if client_id not in registry.client_ids():
            raise HTTPException(404, 'observation session not registered')
        frame = registry.frame(client_id)
        if frame is None:
            raise HTTPException(409, 'session has no observed frame')
        require_observation(registry, client_id, frame, observation_token)
        return {'added': operation(lambda: library.add_document(capture_waypoint(
            frame, client_id, name, entity_index, recording_context(registry, client_id, frame))))}

    @router.post('/import')
    async def import_document(request: Request, waypoints: UploadFile):
        authorize(request)
        if not waypoints.filename or not waypoints.filename.lower().endswith('.json'):
            raise HTTPException(422, 'select a waypoint .json file')
        data = await waypoints.read(MAX_DOCUMENT_BYTES + 1)
        if not data or len(data) > MAX_DOCUMENT_BYTES:
            raise HTTPException(413, 'waypoint import must be 1 byte to 1 MiB')
        def load():
            return library.add_document(json.loads(data.decode('utf-8-sig')))
        return {'added': operation(load)}

    @router.post('/{identity}/rename')
    def rename(request: Request, identity: str, name: str = Query(min_length=1, max_length=200)):
        authorize(request)
        operation(lambda: library.rename(identity, name))
        return {'renamed': identity}

    @router.delete('/{identity}')
    def delete(request: Request, identity: str):
        authorize(request)
        operation(lambda: library.delete(identity))
        return {'deleted': identity}

    return router

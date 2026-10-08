"""Read-only downloads of observations; no writes to game, SQL or host files."""
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from .models import Waypoint
from .telemetry import decode_frame
from .waypoints import waypoint_document


def create_observation_export_router(registry) -> APIRouter:
    router = APIRouter()

    def observed(client_id):
        if client_id not in registry.client_ids():
            raise HTTPException(404, 'observation session not registered')
        frame = registry.frame(client_id)
        if frame is None:
            raise HTTPException(409, 'session has no observed frame')
        return frame

    def provenance(client_id, snapshot):
        return {'session_id': client_id, 'client_id': snapshot.client_id,
                'adapter': snapshot.adapter, 'reported_client_version': snapshot.version,
                'version_verified': False, 'observed_at': snapshot.observed_at,
                'instance_hint': snapshot.instance_hint, 'coordinates': 'raw'}

    def download(document, filename):
        return JSONResponse(document, headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-store',
        })

    @router.get('/waypoint')
    def waypoint(client_id: str = Query(min_length=1, max_length=200),
                 name: str = Query(min_length=1, max_length=200),
                 entity_index: int | None = Query(default=None, ge=0, le=65535)):
        if not name.strip():
            raise HTTPException(422, 'waypoint name is required')
        frame = observed(client_id)
        snapshot = frame.snapshot
        position = snapshot.position
        details = {'kind': 'player', 'character': snapshot.character}
        if entity_index is not None:
            entity = next((e for e in frame.entities if e.client_index == entity_index), None)
            if entity is None:
                raise HTTPException(404, 'entity is not observed in the current frame')
            position = entity.position
            details = {'kind': entity.kind.value, 'name': entity.name,
                       'client_index': entity.client_index,
                       'server_entity_id': entity.server_entity_id,
                       'instance_hint': entity.instance_hint}
        document = waypoint_document([Waypoint(name.strip(), position, source=snapshot.adapter)])
        document['provenance'] = provenance(client_id, snapshot)
        document['observation'] = details
        return download(document, 'observed-waypoint.json')

    @router.get('/path')
    def path(client_id: str = Query(min_length=1, max_length=200)):
        frame = observed(client_id)
        replay = registry._clients.get(client_id)
        if replay is None:
            raise HTTPException(404, 'path export requires a recorded session')
        if replay.position > 10000:
            raise HTTPException(422, 'path export exceeds 10000-frame limit')
        samples = []
        # Export every consumed frame, never the downsampled display trace.
        for payload in replay._frames[:replay.position]:
            snapshot = decode_frame(payload).snapshot
            samples.append({'observed_at': snapshot.observed_at,
                            'position': asdict(snapshot.position),
                            'client_id': snapshot.client_id,
                            'instance_hint': snapshot.instance_hint})
        return download({'schema_version': 1, 'kind': 'live_client_path',
                         'samples': samples,
                         'provenance': provenance(client_id, frame.snapshot)},
                        'observed-path.json')

    return router

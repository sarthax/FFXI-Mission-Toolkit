"""Persistent raw-observation waypoints in a separate toolkit-owned SQLite file."""
from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
import sqlite3
from uuid import uuid4

MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_WAYPOINTS = 1000


def _finite(value):
    try:
        return type(value) in (int, float) and isfinite(value)
    except OverflowError:
        return False


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError(f'invalid {field}')
    return value.strip()


def _metadata(value, keys):
    if not isinstance(value, dict):
        raise ValueError('invalid waypoint metadata')
    result = {}
    for key in keys:
        if key not in value:
            continue
        item = value[key]
        if item is None or isinstance(item, bool):
            result[key] = item
        elif isinstance(item, str) and len(item) <= 200:
            result[key] = item
        elif _finite(item):
            result[key] = item
        else:
            raise ValueError('invalid waypoint metadata value')
    return result


def normalize_document(document: dict) -> list[dict]:
    if (not isinstance(document, dict) or type(document.get('schema_version')) is not int
            or document['schema_version'] != 1 or document.get('kind') != 'live_client_waypoints'):
        raise ValueError('unsupported waypoint document')
    rows = document.get('waypoints')
    if not isinstance(rows, list) or len(rows) > MAX_WAYPOINTS:
        raise ValueError('import allows at most 1000 waypoints')
    normalized = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('position'), dict):
            raise ValueError('invalid waypoint row')
        p = row['position']
        if type(p.get('zone_id')) is not int or not 0 <= p['zone_id'] <= 65535:
            raise ValueError('invalid waypoint zone')
        position = {'zone_id': p['zone_id']}
        for axis in ('x', 'y', 'z', 'heading'):
            value = p.get(axis, 0 if axis == 'heading' else None)
            if not _finite(value):
                raise ValueError('waypoint coordinates must be finite numbers')
            position[axis] = value
        provenance = _metadata(row.get('provenance', document.get('provenance', {})),
            ('session_id', 'session_generation', 'client_id', 'adapter', 'reported_client_version', 'observed_at', 'instance_hint',
             'recorded_frame', 'recorded_segment'))
        provenance.update(version_verified=False, coordinates='raw')
        observation = _metadata(row.get('observation', document.get('observation', {})),
            ('kind', 'character', 'name', 'client_index', 'server_entity_id', 'instance_hint'))
        normalized.append({'name': _text(row.get('name'), 'waypoint name'), 'position': position,
            'source': _text(row.get('source', 'import'), 'waypoint source'),
            'provenance': provenance, 'observation': observation})
    return normalized


class WaypointLibrary:
    def __init__(self, path: Path, *, max_waypoints: int = MAX_WAYPOINTS):
        self.path = Path(path)
        if type(max_waypoints) is not int or not 1 <= max_waypoints <= MAX_WAYPOINTS:
            raise ValueError('invalid library capacity')
        self.max_waypoints = max_waypoints

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        con.execute('CREATE TABLE IF NOT EXISTS waypoints (id TEXT PRIMARY KEY, document TEXT NOT NULL)')
        return con

    def entries(self, *, search: str = '', zone_id: int | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        con = self._connect()
        try:
            rows = [{'id': identity, **json.loads(data)} for identity, data in
                    con.execute('SELECT id, document FROM waypoints ORDER BY rowid')]
        finally:
            con.close()
        return [row for row in rows if search.casefold() in row['name'].casefold()
                and (zone_id is None or row['position']['zone_id'] == zone_id)]

    def add_document(self, document: dict) -> list[dict]:
        rows = normalize_document(document)
        if not rows:
            return []
        encoded = [json.dumps(row, allow_nan=False) for row in rows]
        if sum(len(row.encode()) for row in encoded) > MAX_DOCUMENT_BYTES:
            raise ValueError('waypoint document exceeds size limit')
        added = [{'id': uuid4().hex, **row} for row in rows]
        con = self._connect()
        try:
            with con:
                con.execute('BEGIN IMMEDIATE')
                count = con.execute('SELECT count(*) FROM waypoints').fetchone()[0]
                if count + len(rows) > self.max_waypoints:
                    raise ValueError('waypoint library capacity exceeded')
                existing = [json.loads(row[0]) for row in con.execute('SELECT document FROM waypoints ORDER BY rowid')]
                portable = {'schema_version': 1, 'kind': 'live_client_waypoints', 'waypoints': existing + rows}
                if len(json.dumps(portable, indent=2, allow_nan=False).encode()) > MAX_DOCUMENT_BYTES:
                    raise ValueError('waypoint library exceeds portable document size limit')
                con.executemany('INSERT INTO waypoints VALUES (?, ?)',
                                [(row['id'], data) for row, data in zip(added, encoded)])
        finally:
            con.close()
        return added

    def rename(self, identity: str, name: str):
        name = _text(name, 'waypoint name')
        if not self.path.exists():
            raise KeyError('waypoint not found')
        con = self._connect()
        try:
            with con:
                con.execute('BEGIN IMMEDIATE')
                row = con.execute('SELECT document FROM waypoints WHERE id=?', (identity,)).fetchone()
                if row is None:
                    raise KeyError('waypoint not found')
                document = json.loads(row[0]); document['name'] = name
                con.execute('UPDATE waypoints SET document=? WHERE id=?', (json.dumps(document), identity))
        finally:
            con.close()

    def delete(self, identity: str):
        if not self.path.exists():
            raise KeyError('waypoint not found')
        con = self._connect()
        try:
            with con:
                if con.execute('DELETE FROM waypoints WHERE id=?', (identity,)).rowcount != 1:
                    raise KeyError('waypoint not found')
        finally:
            con.close()

    def export_document(self) -> dict:
        return {'schema_version': 1, 'kind': 'live_client_waypoints',
                'waypoints': [{k: v for k, v in row.items() if k != 'id'} for row in self.entries()]}

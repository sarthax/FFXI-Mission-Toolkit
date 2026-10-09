"""Raw waypoint differences with recording/source/visit isolation, never routing."""
from math import dist, isfinite


def compare_waypoints(frame, session_id: str, entries: list[dict], context: dict) -> dict:
    snapshot = frame.snapshot
    comparable, excluded = [], []
    for entry in entries:
        provenance, p = entry['provenance'], entry['position']
        reason = None
        if p['zone_id'] != snapshot.position.zone_id:
            reason = 'different_zone'
        elif provenance.get('session_id') != session_id:
            reason = 'different_or_unknown_session'
        elif (not isinstance(provenance.get('session_generation'), str)
              or not provenance['session_generation']
              or not isinstance(context.get('session_generation'), str)
              or not context['session_generation']):
            reason = 'recording_generation_unknown'
        elif provenance['session_generation'] != context['session_generation']:
            reason = 'different_recording_generation'
        elif (entry['source'] != snapshot.adapter or provenance.get('adapter') != snapshot.adapter
              or provenance.get('client_id') != snapshot.client_id
              or provenance.get('reported_client_version') != snapshot.version):
            reason = 'different_or_unknown_source'
        elif provenance.get('instance_hint') != snapshot.instance_hint:
            reason = 'different_instance_hint'
        elif (type(provenance.get('recorded_segment')) is not int
              or type(context.get('recorded_segment')) is not int):
            reason = 'recorded_visit_unknown'
        elif provenance['recorded_segment'] != context['recorded_segment']:
            reason = 'different_recorded_visit'
        if reason is None:
            xyz = tuple(getattr(snapshot.position, axis) for axis in ('x', 'y', 'z'))
            target = tuple(p[axis] for axis in ('x', 'y', 'z'))
            delta = {axis: target[i]-xyz[i] for i, axis in enumerate(('x', 'y', 'z'))}
            try:
                distance = dist(xyz, target)
                representable = isfinite(distance) and all(isfinite(value) for value in delta.values())
            except OverflowError:
                representable = False
            if not representable:
                reason = 'difference_out_of_numeric_range'
            else:
                comparable.append({'id': entry['id'], 'name': entry['name'], 'position': p,
                                   'delta': delta, 'distance_raw': distance})
        if reason is not None:
            excluded.append({'id': entry['id'], 'name': entry['name'], 'reason': reason})
    comparable.sort(key=lambda row: (row['distance_raw'], row['name'], row['id']))
    return {'client_id': session_id, 'observed_at': snapshot.observed_at,
            'recorded_frame': context.get('recorded_frame'),
            'zone_id': snapshot.position.zone_id, 'instance_hint': snapshot.instance_hint,
            'waypoints': comparable, 'excluded': excluded, 'units': 'raw_unverified',
            'instance_verified': False, 'coordinate_transform_verified': False,
            'route_verified': False}

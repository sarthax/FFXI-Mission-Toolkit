"""Read-only prioritized impact of explicitly linked Assault shared topics.

Expects projected mission.shared_dependencies entries; no Topaz text matching.
"""

def prioritize(missions):
    topics = {}
    for mission in missions:
        number, zone = mission['number'], mission['zone']
        for dep in mission.get('shared_dependencies', []):
            ident = dep['section_id']
            row = topics.setdefault(ident, {
                'section_id': ident, 'title': dep['title'], 'missions': set(),
                'zones': set(), 'direct_missions': set(), 'zone_missions': set(),
                'port': dep.get('port', 'unreviewed'),
                'validation': dep.get('validation', 'unreviewed'),
            })
            row['missions'].add(number)
            row['zones'].add(zone)
            if 'direct' in dep['scope']:
                row['direct_missions'].add(number)
            if 'zone' in dep['scope']:
                row['zone_missions'].add(number)
    output = []
    for row in topics.values():
        output.append({
            'section_id': row['section_id'], 'title': row['title'],
            'affected_missions': len(row['missions']), 'affected_zones': sorted(row['zones']),
            'mission_ids': sorted(row['missions']),
            'explicit_missions': len(row['direct_missions']),
            'zone_scoped_missions': len(row['zone_missions']),
            'port': row['port'], 'validation': row['validation'],
            'needs_port_evidence': row['port'] not in ('fixed', 'not_applicable'),
            'needs_test_evidence': row['validation'] not in ('fixed', 'not_applicable'),
            'confirmed_blocker': row['port'] == 'blocked' or row['validation'] == 'blocked',
        })
    return sorted(output, key=lambda r: (not r['confirmed_blocker'], -r['affected_missions'], r['section_id']))

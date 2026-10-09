"""Additive raw entity diagnostics remain unverified and provider-neutral."""
import json
from pathlib import Path

import pytest

from workbench.runtime.live_client.feed import TelemetryFeedAdapter
from workbench.runtime.live_client.telemetry import decode_frame
from workbench.runtime.live_client.viewer import viewer_projection

CAPTURE = Path(__file__).parent / 'fixtures/live_client/ashita_v4_runtime_anonymized.jsonl'


def payload():
    rows = [json.loads(line) for line in CAPTURE.read_text().splitlines()]
    return next(row for row in rows if row['entities'])


@pytest.mark.parametrize('field,value', [
    ('raw_entity_type', -1), ('raw_entity_type', 256), ('raw_entity_type', True),
    ('raw_spawn_flags', -1), ('raw_spawn_flags', 4294967296), ('raw_spawn_flags', '123'),
    ('raw_status', False), ('raw_status', 1.5), ('raw_status', float('nan')),
    ('target_roles', 'target'), ('target_roles', ['pet']),
    ('target_roles', ['target', 'target']), ('target_roles', [None]),
    ('target_roles', [['target']]), ('target_roles', ['target', 'subtarget', 'target']),
])
def test_invalid_entity_state_retains_last_good_frame(field, value):
    good = payload(); feed = TelemetryFeedAdapter(good['client_id'])
    before = feed.ingest(good)
    bad = json.loads(json.dumps(good)); bad['observed_at'] += 1
    bad['entities'][0][field] = value
    with pytest.raises(ValueError):
        feed.ingest(bad)
    assert feed._latest is before
    assert feed.supports_writes is False and feed.version_verified is False


def test_legacy_and_other_provider_diagnostics_are_not_inferred():
    good = payload(); frame = decode_frame(good)
    item, = frame.entities
    assert item.raw_entity_type is None and item.raw_spawn_flags is None and item.raw_status is None
    assert item.target_roles == ()
    good['adapter'] = 'future-native-readonly'
    good['entities'][0].update(raw_entity_type=255, raw_spawn_flags=0, raw_status=0,
                              target_roles=['target'])
    frame = decode_frame(good)
    projected = viewer_projection(frame, zone_id=50, client_id=good['client_id'])
    row, = projected['entities']
    assert row['raw_entity_type'] == 255 and row['raw_spawn_flags'] == 0 and row['raw_status'] == 0
    assert row['kind'] == 'unknown' and row['target_roles'] == ['target']
    assert row['server_entity_id'] is None and row['instance_hint'] is None
    assert viewer_projection(frame, zone_id=50, client_id='other')['entities'] == []

"""Trusted runtime interface must remain scoped and fail closed."""
from workbench.devtools.research.entity_runtime_provider import TrustedRuntimeProvider


def test_reads_exactly_one_requested_instance():
    calls = []
    def read(**kwargs):
        calls.append(kwargs)
        return dict(source="server_runtime", zone=87, server_entity_id=17215539,
                    instance_id="alpha", observed_at=1000.0, state="active")
    adapter = TrustedRuntimeProvider(read)
    result = adapter.inspect(zone=87, server_entity_id=17215539, instance_id="alpha", now=1001.)
    assert result["runtime_status"] == "active"
    assert calls == [dict(zone=87, server_entity_id=17215539, instance_id="alpha")]


def test_missing_server_feed_does_not_claim_despawn():
    adapter = TrustedRuntimeProvider(lambda **kwargs: None)
    result = adapter.inspect(zone=87, server_entity_id=17215539, instance_id="alpha", now=1001.)
    assert result["runtime_status"] == "unknown"


def test_transport_error_fails_closed():
    def unavailable(**kwargs):
        raise TimeoutError("server unreachable")
    result = TrustedRuntimeProvider(unavailable).inspect(
        zone=87, server_entity_id=17215539, instance_id="alpha", now=1001.)
    assert result["runtime_status"] == "unknown"

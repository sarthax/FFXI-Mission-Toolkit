"""Local peer token and lifecycle boundaries; simulated clients only."""
from dataclasses import replace

from workbench.runtime.live_client.bridge_peers import LocalPeerRegistry, PeerIdentity
from workbench.runtime.live_client.bridge_protocol import BridgeEnvelope, BridgeKind, BridgeLane


def message(identity):
    return BridgeEnvelope(1, BridgeLane.TELEMETRY, BridgeKind.OBSERVATION,
                          identity.client_id, identity.session_id, identity.generation,
                          1, None, b'{}')


def test_registration_token_and_expiry_fail_closed():
    registry = LocalPeerRegistry(ttl_seconds=5)
    client = PeerIdentity("client-a", "session-one", "generation-one")
    token = registry.issue(client, now=100)
    assert registry.authenticate(client, token, now=100)
    assert registry.accepts(message(client), token, now=104)
    assert not registry.authenticate(client, token, now=105)
    assert not registry.authenticate(client, token + "x", now=102)
    assert not registry.accepts(message(replace(client, session_id="other")), token, now=102)
    assert not registry.accepts(message(replace(client, generation="other")), token, now=102)


def test_replacing_client_revokes_original_generation_and_token():
    registry = LocalPeerRegistry(ttl_seconds=10)
    first = PeerIdentity("client-a", "old-session", "old-generation")
    old_token = registry.issue(first, now=10)
    next_one = replace(first, session_id="new-session", generation="new-generation")
    new_token = registry.issue(next_one, now=11)
    assert not registry.accepts(message(first), old_token, now=12)
    assert not registry.accepts(message(next_one), old_token, now=12)
    assert registry.accepts(message(next_one), new_token, now=12)
    registry.revoke("client-a")
    assert not registry.accepts(message(next_one), new_token, now=12)


def test_renewal_requires_correct_live_identity_and_secret():
    registry = LocalPeerRegistry(ttl_seconds=5)
    identity = PeerIdentity("client-a", "session", "generation")
    token = registry.issue(identity, now=100)
    assert not registry.refresh(identity, "wrong", now=102)
    assert registry.refresh(identity, token, now=103)
    assert registry.authenticate(identity, token, now=107)
    assert not registry.refresh(identity, token, now=108)


def test_two_clients_have_independent_lifecycles():
    registry = LocalPeerRegistry(ttl_seconds=5)
    a = PeerIdentity("a", "session", "one")
    b = PeerIdentity("b", "session", "one")
    a_token = registry.issue(a, now=100)
    b_token = registry.issue(b, now=100)
    registry.revoke("a")
    assert not registry.accepts(message(a), a_token, now=101)
    assert registry.accepts(message(b), b_token, now=101)

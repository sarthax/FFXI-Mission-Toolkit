"""Optional Live Client errors must not prevent toolkit startup."""
from workbench.runtime.live_client.registry import ReplayRegistry
from workbench.runtime.live_client.startup import initialize_live_client


def test_missing_replay_is_nonfatal(tmp_path):
    registry = ReplayRegistry()
    settings = {"live_client_source": "replay", "live_client_auto_connect": "1",
                "live_client_replay_file": str(tmp_path / "missing.jsonl"),
                "live_client_replay_client": "test-client-01"}
    error = initialize_live_client(registry, settings, {})
    assert error is not None and "Live Client unavailable" in error
    assert registry.client_ids() == ()


def test_missing_file_feed_is_nonfatal(tmp_path):
    registry = ReplayRegistry()
    settings = {"live_client_source": "file_feed", "live_client_auto_connect": "1",
                "live_client_feed_file": str(tmp_path / "missing.jsonl"),
                "live_client_feed_client": "test-client-01"}
    error = initialize_live_client(registry, settings, {})
    assert "does not exist" in error
    assert registry.client_ids() == ()


def test_disabled_starts_clean():
    registry = ReplayRegistry()
    assert initialize_live_client(registry, {"live_client_source": "disabled"}, {}) is None
    assert registry.client_ids() == ()

"""Unit tests for the Config configuration manager."""

import json
import os
import tempfile
from pathlib import Path

from analyzer.config import Config


class TestConfigDefaults:
    """Test that Config has correct default values."""

    def test_default_values(self):
        config = Config()
        assert config.window_width == 900
        assert config.window_height == 600
        assert config.port == 52985
        assert config.max_packets == 5000
        assert config.filter_string == ""
        assert config.auto_scroll is True


class TestConfigLoad:
    """Test Config.load behavior with various inputs."""

    def test_load_valid_config(self, tmp_path):
        path = str(tmp_path / "config.json")
        data = {
            "window_width": 1024,
            "window_height": 768,
            "port": 9999,
            "max_packets": 10000,
            "filter_string": "hello",
            "auto_scroll": False,
        }
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        config = Config.load(path)
        assert config.window_width == 1024
        assert config.window_height == 768
        assert config.port == 9999
        assert config.max_packets == 10000
        assert config.filter_string == "hello"
        assert config.auto_scroll is False

    def test_load_missing_file_returns_defaults(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        config = Config.load(path)
        assert config.window_width == 900
        assert config.window_height == 600
        assert config.port == 52985
        assert config.max_packets == 5000
        assert config.filter_string == ""
        assert config.auto_scroll is True

    def test_load_corrupt_json_returns_defaults(self, tmp_path):
        path = str(tmp_path / "config.json")
        Path(path).write_text("not valid json {{{{", encoding="utf-8")

        config = Config.load(path)
        assert config.window_width == 900
        assert config.window_height == 600

    def test_load_non_dict_json_returns_defaults(self, tmp_path):
        path = str(tmp_path / "config.json")
        Path(path).write_text("[1, 2, 3]", encoding="utf-8")

        config = Config.load(path)
        assert config.window_width == 900

    def test_load_clamps_values_above_max(self, tmp_path):
        path = str(tmp_path / "config.json")
        data = {
            "window_width": 9999,
            "window_height": 5000,
            "port": 70000,
            "max_packets": 999999,
        }
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        config = Config.load(path)
        assert config.window_width == 3840
        assert config.window_height == 2160
        assert config.port == 65535
        assert config.max_packets == 100000

    def test_load_clamps_values_below_min(self, tmp_path):
        path = str(tmp_path / "config.json")
        data = {
            "window_width": 100,
            "window_height": 50,
            "port": 500,
            "max_packets": 10,
        }
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        config = Config.load(path)
        assert config.window_width == 400
        assert config.window_height == 300
        assert config.port == 1024
        assert config.max_packets == 100

    def test_load_missing_keys_use_defaults(self, tmp_path):
        path = str(tmp_path / "config.json")
        # Only some keys present
        data = {"window_width": 1200}
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        config = Config.load(path)
        assert config.window_width == 1200
        assert config.window_height == 600  # default
        assert config.port == 52985  # default
        assert config.max_packets == 5000  # default
        assert config.filter_string == ""  # default
        assert config.auto_scroll is True  # default

    def test_load_invalid_types_use_defaults(self, tmp_path):
        path = str(tmp_path / "config.json")
        data = {
            "window_width": "not a number",
            "window_height": None,
            "port": [1234],
            "max_packets": {"value": 100},
            "filter_string": 12345,
            "auto_scroll": "yes",
        }
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        config = Config.load(path)
        assert config.window_width == 900  # default
        assert config.window_height == 600  # default
        assert config.port == 52985  # default
        assert config.max_packets == 5000  # default
        assert config.filter_string == ""  # default
        assert config.auto_scroll is True  # default

    def test_load_boolean_values_not_treated_as_int(self, tmp_path):
        """Booleans are technically int subclass in Python; ensure they use defaults."""
        path = str(tmp_path / "config.json")
        data = {
            "window_width": True,
            "window_height": False,
            "port": True,
            "max_packets": False,
        }
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        config = Config.load(path)
        assert config.window_width == 900  # default
        assert config.window_height == 600  # default
        assert config.port == 52985  # default
        assert config.max_packets == 5000  # default

    def test_load_truncates_long_filter_string(self, tmp_path):
        path = str(tmp_path / "config.json")
        long_str = "x" * 500
        data = {"filter_string": long_str}
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        config = Config.load(path)
        assert len(config.filter_string) == 256
        assert config.filter_string == "x" * 256

    def test_load_auto_scroll_non_bool_uses_default(self, tmp_path):
        path = str(tmp_path / "config.json")
        data = {"auto_scroll": 1}
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        config = Config.load(path)
        assert config.auto_scroll is True  # default

    def test_load_float_values_are_truncated_to_int(self, tmp_path):
        path = str(tmp_path / "config.json")
        data = {"window_width": 1024.7, "port": 9999.9}
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        config = Config.load(path)
        assert config.window_width == 1024
        assert config.port == 9999


class TestConfigSave:
    """Test Config.save writes valid JSON."""

    def test_save_creates_file(self, tmp_path):
        path = str(tmp_path / "config.json")
        config = Config()
        config.save(path)

        assert Path(path).exists()

    def test_save_writes_valid_json(self, tmp_path):
        path = str(tmp_path / "config.json")
        config = Config(window_width=1024, port=8080)
        config.save(path)

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["window_width"] == 1024
        assert data["port"] == 8080

    def test_save_pretty_formats(self, tmp_path):
        path = str(tmp_path / "config.json")
        config = Config()
        config.save(path)

        content = Path(path).read_text(encoding="utf-8")
        # Pretty-printed JSON has newlines and indentation
        assert "\n" in content
        assert "  " in content

    def test_save_all_fields(self, tmp_path):
        path = str(tmp_path / "config.json")
        config = Config(
            window_width=1920,
            window_height=1080,
            port=12345,
            max_packets=2000,
            filter_string="test filter",
            auto_scroll=False,
        )
        config.save(path)

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data == {
            "window_width": 1920,
            "window_height": 1080,
            "port": 12345,
            "max_packets": 2000,
            "filter_string": "test filter",
            "auto_scroll": False,
        }


class TestConfigRoundTrip:
    """Test save then load preserves values."""

    def test_round_trip_preserves_values(self, tmp_path):
        path = str(tmp_path / "config.json")
        original = Config(
            window_width=1280,
            window_height=720,
            port=9000,
            max_packets=8000,
            filter_string="zone",
            auto_scroll=False,
        )
        original.save(path)

        loaded = Config.load(path)
        assert loaded.window_width == original.window_width
        assert loaded.window_height == original.window_height
        assert loaded.port == original.port
        assert loaded.max_packets == original.max_packets
        assert loaded.filter_string == original.filter_string
        assert loaded.auto_scroll == original.auto_scroll

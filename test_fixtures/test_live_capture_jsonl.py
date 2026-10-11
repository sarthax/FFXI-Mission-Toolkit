"""Offline native packet session adapter tests."""
import unittest

from workbench.captures.live_capture_jsonl import parse_session


def row(sequence, **changes):
    import json
    item = dict(schema_version=1, client_id="ashita-a", session_id="s1",
                sequence=sequence, observed_at_ns=1760000000000000000 + sequence,
                direction="incoming", opcode=40, raw_hex="28040000",
                is_injected=False, is_blocked=False, dropped_before=0)
    item.update(changes)
    return (json.dumps(item) + "\n").encode()


class NativeLiveCaptureJsonlTests(unittest.TestCase):
    def test_two_rows_preserve_offsets(self):
        data = row(1) + row(2)
        parsed = parse_session(data)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0][2:], (0, len(row(1))))
        self.assertEqual(parsed[1][2:], (len(row(1)), len(data)))

    def test_reject_truncated_session(self):
        with self.assertRaises(ValueError):
            parse_session(row(1).rstrip(b"\n"))

    def test_reject_sequence_gap(self):
        with self.assertRaises(ValueError):
            parse_session(row(1) + row(3))

    def test_reject_regressed_drops(self):
        with self.assertRaises(ValueError):
            parse_session(row(1, dropped_before=2) + row(2, dropped_before=1))

    def test_reject_unknown_fields(self):
        with self.assertRaises(ValueError):
            parse_session(row(1, arbitrary="bad"))

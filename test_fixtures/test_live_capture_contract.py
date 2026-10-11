"""Contract tests for proposed native read-only packet recorder."""
import unittest

from workbench.captures.live_capture_contract import LiveCaptureSequence, LivePacketEnvelope


def sample(**changes):
    value = dict(
        schema_version=1, client_id="ashita-a", session_id="session-1",
        sequence=1, observed_at_ns=1_760_000_000_000_000_000,
        direction="incoming", opcode=0x28, raw_hex="00112233",
        is_injected=False, is_blocked=False, dropped_before=0,
    )
    value.update(changes)
    return value


class LiveCaptureContractTests(unittest.TestCase):
    def test_preserves_raw_bytes(self):
        packet = LivePacketEnvelope.from_mapping(sample())
        self.assertEqual(packet.raw_bytes, b"\\x00\\x11\\x22\\x33")

    def test_rejects_invalid_payloads(self):
        for changes in (
            {"raw_hex": "XX"}, {"raw_hex": "A"}, {"raw_hex": ""},
            {"is_blocked": 0}, {"sequence": True}, {"schema_version": 2},
            {"direction": "sideways"}, {"client_id": ""},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                LivePacketEnvelope.from_mapping(sample(**changes))

    def test_sequence_and_drop_counter(self):
        check = LiveCaptureSequence()
        check.accept(LivePacketEnvelope.from_mapping(sample()))
        check.accept(LivePacketEnvelope.from_mapping(sample(sequence=2, dropped_before=0)))
        with self.assertRaises(ValueError):
            check.accept(LivePacketEnvelope.from_mapping(sample(sequence=4, dropped_before=0)))
        with self.assertRaises(ValueError):
            check.accept(LivePacketEnvelope.from_mapping(sample(sequence=3, dropped_before=0)))

    def test_clients_are_independent(self):
        check = LiveCaptureSequence()
        check.accept(LivePacketEnvelope.from_mapping(sample(client_id="a")))
        check.accept(LivePacketEnvelope.from_mapping(sample(client_id="b")))

    def test_reported_loss_allows_sequence_gap(self):
        check = LiveCaptureSequence()
        check.accept(LivePacketEnvelope.from_mapping(sample()))
        check.accept(LivePacketEnvelope.from_mapping(sample(sequence=4, dropped_before=2)))

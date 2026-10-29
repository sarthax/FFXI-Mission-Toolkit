"""Offline tests for manifest history snapshots."""
import json
import tempfile
import unittest
from pathlib import Path
from workbench.client.retail.history import store_snapshot, search


def payload(size=9, transfer="30220101_0/Direct/ROM/1/1.DAT.slc"):
    return json.dumps({"schema": 1, "source": "playonline-patch-manifest:ffxi",
      "files": [{"file": "ROM/1/1.DAT", "versions": [
        {"stamp": "30220101_0", "decoded_bytes": size, "transfer_bytes": 5,
         "server_path": transfer}]}]}).encode()


class ManifestHistoryTests(unittest.TestCase):
    def test_snapshots_union_and_repeat_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one = store_snapshot(payload(), root, observed_utc="2022-01-01T00:00:00Z")
            two = store_snapshot(payload(), root, observed_utc="2026-10-22T00:00:00Z")
            self.assertEqual(one["sha256"], two["sha256"])
            self.assertEqual(len(list((root / "snapshots").glob("*.json"))), 1)
            self.assertEqual(len((root / "observations.jsonl").read_text().splitlines()), 2)
            rows = search(root, stamp="30220101_0")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["availability"], "UNKNOWN")

    def test_conflicts_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_snapshot(payload(), root)
            store_snapshot(payload(size=10), root)
            self.assertEqual(search(root)[0]["availability"], "CONFLICTING_MANIFESTS")

    def test_reject_invalid_paths_and_stamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            for broken in [payload(transfer="../bad"), payload().replace(b"30220101_0", b"bad")]:
                with self.assertRaises(ValueError):
                    store_snapshot(broken, Path(tmp))

    def test_tampering_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = store_snapshot(payload(), root)
            (root / "snapshots" / (record["sha256"] + ".json")).write_text("{}")
            with self.assertRaises(ValueError):
                search(root)


if __name__ == "__main__":
    unittest.main()

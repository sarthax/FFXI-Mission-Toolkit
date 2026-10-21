#!/usr/bin/env python3
"""Synthetic-only Wardrobe 5-8 sidecar model invariants; no retail bytes."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.wardrobe_2019_sidecar_model import (
    HypotheticalStoreRouter, StoreToken, describe_hypothetical_sidecar,
    SIDECAR_BYTES_PER_STORE, LEGACY_ARRAY_START, LEGACY_CURSOR_START,
    SLOTS_PER_CONTAINER, RECORD_SIZE,
)


class Wardrobe2019SidecarModelTests(unittest.TestCase):
    def test_hypothetical_region_never_consumes_legacy_cursor(self):
        m = describe_hypothetical_sidecar()
        self.assertEqual(m["design_status"], "HYPOTHETICAL_SYNTHETIC_ONLY")
        self.assertEqual(m["proposed_sidecar_container_ids"], [13, 14, 15, 16])
        self.assertEqual(m["legacy_record_array_exclusive_end_offset"], 0x14D5C)
        self.assertEqual(m["existing_cursor_start_offset"], 0x14D5C)
        self.assertTrue(m["legacy_memory_layout_unchanged"])
        self.assertTrue(m["legacy_cursor_untouched_by_model"])
        self.assertTrue(m["model_allocates_no_memory_or_item_buffers"])
        self.assertEqual(SIDECAR_BYTES_PER_STORE, 4 * 81 * 44)
        self.assertEqual(SIDECAR_BYTES_PER_STORE, 14256)
        self.assertEqual(m["client_patch_and_packet_support"], "NOT_IMPLEMENTED")
        self.assertEqual(m["recycler_id_not_in_scope"], 17)

    def test_default_simulation_refuses_new_container_ids(self):
        registry = HypotheticalStoreRouter()
        token = registry.register(0)
        self.assertIsNotNone(token)
        active = registry.activate(0)
        self.assertEqual(active, token)
        original = registry.resolve(token, 12, 80)
        self.assertIsNotNone(original)
        self.assertEqual(original.region, "LEGACY_ARRAY")
        self.assertEqual(original.offset + RECORD_SIZE, LEGACY_CURSOR_START)
        self.assertIsNone(registry.resolve(token, 13, 0))
        self.assertIsNone(registry.resolve(token, 16, 80))
        self.assertIsNone(registry.resolve(token, 17, 0))

    def test_sidecar_simulation_has_separate_contiguous_offsets(self):
        registry = HypotheticalStoreRouter()
        token = registry.register(0)
        registry.activate(0)
        for cid in (13, 14, 15, 16):
            for slot in (0, 80):
                with self.subTest(container=cid,slot=slot):
                    route = registry.resolve(token, cid, slot, simulate_extension=True)
                    self.assertIsNotNone(route)
                    self.assertEqual(route.region, "SIMULATED_SIDECAR")
                    self.assertEqual(route.offset, ((cid - 13) * 81 + slot) * 44)
                    self.assertLessEqual(route.offset + RECORD_SIZE, SIDECAR_BYTES_PER_STORE)
        last = registry.resolve(token, 16, 80, simulate_extension=True)
        self.assertEqual(last.offset + RECORD_SIZE, SIDECAR_BYTES_PER_STORE)
        for cid in (17, 18, 255, -1):
            self.assertIsNone(registry.resolve(token, cid, 0, simulate_extension=True))
        for slot in (-1, 81, 255):
            self.assertIsNone(registry.resolve(token, 13, slot, simulate_extension=True))

    def test_manager_store_switch_requires_current_token(self):
        r = HypotheticalStoreRouter(manager_slot_limit=4)
        token0 = r.register(0)
        token1 = r.register(1)
        self.assertIsNotNone(token0)
        self.assertIsNotNone(token1)
        r.activate(0)
        self.assertIsNotNone(r.resolve(token0, 13, 10, simulate_extension=True))
        self.assertIsNone(r.resolve(token1, 13, 10, simulate_extension=True))
        r.activate(1)
        self.assertIsNone(r.resolve(token0, 13, 10, simulate_extension=True))
        second = r.resolve(token1, 13, 10, simulate_extension=True)
        self.assertEqual(second.manager_index, 1)
        self.assertEqual(second.generation, token1.generation)
        r.activate(0)
        self.assertIsNotNone(r.resolve(token0, 13, 10, simulate_extension=True))

    def test_reset_retire_and_reuse_invalidate_stale_tokens(self):
        r = HypotheticalStoreRouter()
        first = r.register(2)
        r.activate(2)
        self.assertTrue(r.resolve(first, 16, 80, simulate_extension=True))
        replacement = r.reset(2)
        self.assertNotEqual(first.generation, replacement.generation)
        self.assertIsNone(r.resolve(first, 16, 80, simulate_extension=True))
        self.assertIsNone(r.resolve(replacement, 16, 80, simulate_extension=True))
        r.activate(2)
        self.assertIsNotNone(r.resolve(replacement, 16, 80, simulate_extension=True))
        self.assertTrue(r.retire(2))
        self.assertIsNone(r.resolve(replacement, 13, 0, simulate_extension=True))
        later = r.register(2)
        self.assertGreater(later.generation, replacement.generation)
        r.activate(2)
        self.assertIsNone(r.resolve(first, 13, 0, simulate_extension=True))
        self.assertIsNotNone(r.resolve(later, 13, 0, simulate_extension=True))

    def test_unknown_slots_and_duplicate_registration_fail_closed(self):
        r = HypotheticalStoreRouter(manager_slot_limit=3)
        for invalid in (-1, 3, 255, True, 1.0, "1"):
            self.assertIsNone(r.register(invalid))
            self.assertIsNone(r.activate(invalid))
            self.assertIsNone(r.reset(invalid))
            self.assertFalse(r.retire(invalid))
        self.assertIsNone(r.activate(0))
        token = r.register(0)
        self.assertIsNone(r.register(0))
        self.assertIsNone(r.reset(1))
        self.assertFalse(r.retire(1))
        r.activate(0)
        self.assertIsNone(r.resolve(StoreToken(0, token.generation + 1), 13, 0,
                                    simulate_extension=True))
        for v in (True, 1.0, "13"):
            self.assertIsNone(r.resolve(token, v, 0, simulate_extension=True))
            self.assertIsNone(r.resolve(token, 13, v, simulate_extension=True))
        self.assertIsNone(r.resolve(token, 13, 0, simulate_extension=1))

    def test_manager_limit_is_only_synthetic_guard(self):
        for bad in (0, 33, -1, True, 2.0, "16"):
            with self.assertRaises(ValueError):
                HypotheticalStoreRouter(bad)
        self.assertIsNotNone(HypotheticalStoreRouter(1).register(0))
        self.assertEqual(LEGACY_ARRAY_START + 13 * SLOTS_PER_CONTAINER * RECORD_SIZE,
                         LEGACY_CURSOR_START)


if __name__ == "__main__":
    unittest.main()

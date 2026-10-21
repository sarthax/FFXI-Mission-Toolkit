#!/usr/bin/env python3
"""Pure synthetic bank-A/B mapping contract, not a running server integration."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from workbench.client.wardrobe_bank_contract import (
    BankContractError, OfflineBankSwitchEvidence,
    VISIBLE_IDS, PROPOSED_SECOND_BANK, client_visible_to_canonical,
    server_canonical_to_visible, require_offline_bank_switch,
)


class TestLegacyBankMapping(unittest.TestCase):
    def test_every_visible_id_round_trips_in_both_banks(self):
        self.assertEqual(VISIBLE_IDS, (8, 10, 11, 12))
        self.assertEqual(PROPOSED_SECOND_BANK, (13, 14, 15, 16))
        for bank in ("A", "B"):
            for visible in range(13):
                canonical = client_visible_to_canonical(visible, bank)
                self.assertEqual(server_canonical_to_visible(canonical, bank), visible)
        self.assertEqual(client_visible_to_canonical(9, "B"), 9)
        self.assertEqual(server_canonical_to_visible(9, "B"), 9)

    def test_never_exposes_other_bank_or_modern_id_to_2019_client(self):
        for container in range(13, 17):
            with self.assertRaisesRegex(BankContractError, "bank B ID"):
                server_canonical_to_visible(container, "A")
            with self.assertRaisesRegex(BankContractError, "outside original"):
                client_visible_to_canonical(container, "B")
        for visible in VISIBLE_IDS:
            with self.assertRaisesRegex(BankContractError, "bank A wardrobe"):
                server_canonical_to_visible(visible, "B")

    def test_unsupported_ids_and_unverified_bank_fail_closed(self):
        for value in (-1, 17, None, True, "9"):
            for bank in ("A", "B"):
                with self.assertRaises(BankContractError):
                    client_visible_to_canonical(value, bank)
        for bank in (None, "auto", "", "C"):
            with self.assertRaisesRegex(BankContractError, "not verified"):
                client_visible_to_canonical(8, bank)

    def test_switch_requires_every_explicit_guard(self):
        evidence = dict(
            feature_enabled=True, character_authenticated=True,
            session_disconnected=True, inventory_transactions_idle=True,
            writes_durably_persisted=True, no_unresolved_equipped_items=True,
            gearset_references_validated=True, canonical_storage_ready=True,
        )
        self.assertEqual(require_offline_bank_switch(
            OfflineBankSwitchEvidence(**evidence), "B"), "B")
        for flag in evidence:
            failing = dict(evidence)
            failing[flag] = False
            with self.subTest(flag=flag), self.assertRaisesRegex(
                BankContractError, flag
            ):
                require_offline_bank_switch(
                    OfflineBankSwitchEvidence(**failing), "B")

    def test_safe_defaults_refuse_every_switch(self):
        with self.assertRaisesRegex(BankContractError, "feature_enabled"):
            require_offline_bank_switch(OfflineBankSwitchEvidence(), "A")


if __name__ == "__main__":
    unittest.main()

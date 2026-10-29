"""Pure, synthetic reference contract for a hypothetical legacy Wardrobe bank.

NO SERVER ADAPTER. NO PACKET MUTATION. NO CLIENT PATCH.

The 2019 client only supports visible wardrobe IDs 8,10,11,12.
Proposed hidden backing IDs 13..16 do not exist in the current DSP server.
All mapping requires a manually verified, stable, per-session bank.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VISIBLE_IDS = (8, 10, 11, 12)
PROPOSED_SECOND_BANK = (13, 14, 15, 16)
LEGACY_CONTAINER_IDS = frozenset(range(13))
VISIBLE_TO_SECOND = dict(zip(VISIBLE_IDS, PROPOSED_SECOND_BANK))
SECOND_TO_VISIBLE = dict(zip(PROPOSED_SECOND_BANK, VISIBLE_IDS))
Bank = Literal["A", "B"]


class BankContractError(ValueError):
    """Fail-closed: a guessed or unsafe mapping must never be used."""


def _check_bank(bank: Bank) -> None:
    if bank not in ("A", "B"):
        raise BankContractError("bank is not verified A or B")


def client_visible_to_canonical(container: int, bank: Bank) -> int:
    """Hypothetical server ingress mapping, not a runnable protocol adapter."""
    _check_bank(bank)
    if type(container) is not int or container not in LEGACY_CONTAINER_IDS:
        raise BankContractError("2019 client container outside original 0..12")
    if bank == "B":
        return VISIBLE_TO_SECOND.get(container, container)
    return container


def server_canonical_to_visible(container: int, bank: Bank) -> int:
    """Hypothetical server egress mapping; hidden bank IDs are REFUSED."""
    _check_bank(bank)
    if type(container) is not int:
        raise BankContractError("invalid canonical container type")
    if bank == "A":
        if container not in LEGACY_CONTAINER_IDS:
            raise BankContractError("bank B ID cannot appear in bank A")
        return container
    if container in SECOND_TO_VISIBLE:
        return SECOND_TO_VISIBLE[container]
    if container in VISIBLE_IDS:
        raise BankContractError("bank A wardrobe must not appear in bank B")
    if container in LEGACY_CONTAINER_IDS:
        return container  # Includes id=9, Mog Safe 2; never remap it.
    raise BankContractError("unknown canonical container")


@dataclass(frozen=True)
class OfflineBankSwitchEvidence:
    feature_enabled: bool = False
    character_authenticated: bool = False
    session_disconnected: bool = False
    inventory_transactions_idle: bool = False
    writes_durably_persisted: bool = False
    no_unresolved_equipped_items: bool = False
    gearset_references_validated: bool = False
    canonical_storage_ready: bool = False


def require_offline_bank_switch(evidence: OfflineBankSwitchEvidence,
                                requested_bank: Bank) -> str:
    """Pure acceptance contract, never performs a switch."""
    _check_bank(requested_bank)
    missing = [name for name, yes in vars(evidence).items() if not yes]
    if missing:
        raise BankContractError("bank switch refused: " + ", ".join(missing))
    return requested_bank

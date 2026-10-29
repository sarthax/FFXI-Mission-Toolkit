"""Pure, non-runtime thought experiment for 2019 Wardrobe 5-8 sidecar storage.

No retail DLL patching, process memory, packet I/O or item bytes. This model
illustrates separation from the 13-container legacy layout only. It does not
establish that a real client can allocate, populate, equip, persist or display
additional containers.
"""
from __future__ import annotations

from dataclasses import dataclass

LEGACY_COUNT = 13
WARDROBE_5_TO_8_IDS = (13, 14, 15, 16)
RECYCLER_ID = 17  # Not part of the four-Wardrobe sidecar experiment.
SLOTS_PER_CONTAINER = 81
RECORD_SIZE = 44
LEGACY_ARRAY_START = 0x9860
LEGACY_CURSOR_START = 0x14D5C
SIDECAR_BYTES_PER_STORE = len(WARDROBE_5_TO_8_IDS) * SLOTS_PER_CONTAINER * RECORD_SIZE


@dataclass(frozen=True)
class StoreToken:
    manager_index: int
    generation: int


@dataclass(frozen=True)
class RecordRoute:
    region: str
    offset: int
    container_id: int
    slot_id: int
    manager_index: int
    generation: int


def describe_hypothetical_sidecar() -> dict:
    """Scalar planning metadata, never a claim of runtime support."""
    return {
        "design_status": "HYPOTHETICAL_SYNTHETIC_ONLY",
        "legacy_container_ids": list(range(LEGACY_COUNT)),
        "proposed_sidecar_container_ids": list(WARDROBE_5_TO_8_IDS),
        "recycler_id_not_in_scope": RECYCLER_ID,
        "slots_per_container": SLOTS_PER_CONTAINER,
        "record_size_bytes": RECORD_SIZE,
        "legacy_record_array_start_offset": LEGACY_ARRAY_START,
        "legacy_record_array_exclusive_end_offset": (
            LEGACY_ARRAY_START + LEGACY_COUNT * SLOTS_PER_CONTAINER * RECORD_SIZE
        ),
        "existing_cursor_start_offset": LEGACY_CURSOR_START,
        "sidecar_bytes_per_store": SIDECAR_BYTES_PER_STORE,
        "legacy_memory_layout_unchanged": True,
        "legacy_cursor_untouched_by_model": True,
        "model_allocates_no_memory_or_item_buffers": True,
        "client_patch_and_packet_support": "NOT_IMPLEMENTED",
        "required_runtime_evidence": [
            "Allocation size and ownership for every manager-selected store",
            "Safe sidecar allocation, reset, switch and teardown hooks",
            "Complete item accessors, packet ingress/egress and UI consumers",
            "Per-session packet 0x1C format and server-side data persistence",
        ],
    }


class HypotheticalStoreRouter:
    """Generation-aware address *metadata* for one active synthetic store.

    manager_slot_limit is a MODEL guard, NOT a verified 2019 maximum.
    This class never reads/writes client memory or allocates record storage.
    """

    def __init__(self, manager_slot_limit: int = 16) -> None:
        if type(manager_slot_limit) is not int or not (1 <= manager_slot_limit <= 32):
            raise ValueError("model manager slot bound must be 1..32")
        self._limit = manager_slot_limit
        self._generations: dict[int, int] = {}
        self._next_generation = 1
        self._active: StoreToken | None = None

    def _valid_index(self, manager_index: int) -> bool:
        return type(manager_index) is int and 0 <= manager_index < self._limit

    def register(self, manager_index: int) -> StoreToken | None:
        if not self._valid_index(manager_index) or manager_index in self._generations:
            return None
        token = StoreToken(manager_index, self._next_generation)
        self._next_generation += 1
        self._generations[manager_index] = token.generation
        return token

    def activate(self, manager_index: int) -> StoreToken | None:
        if not self._valid_index(manager_index):
            return None
        generation = self._generations.get(manager_index)
        if generation is None:
            return None
        token = StoreToken(manager_index, generation)
        self._active = token
        return token

    def reset(self, manager_index: int) -> StoreToken | None:
        if not self._valid_index(manager_index) or manager_index not in self._generations:
            return None
        token = StoreToken(manager_index, self._next_generation)
        self._next_generation += 1
        self._generations[manager_index] = token.generation
        if self._active is not None and self._active.manager_index == manager_index:
            self._active = None
        return token

    def retire(self, manager_index: int) -> bool:
        if not self._valid_index(manager_index) or manager_index not in self._generations:
            return False
        del self._generations[manager_index]
        if self._active is not None and self._active.manager_index == manager_index:
            self._active = None
        return True

    def resolve(self, token: StoreToken, container_id: int, slot_id: int, *,
                simulate_extension: bool = False) -> RecordRoute | None:
        """Return only bounded region/offset metadata, otherwise None."""
        if type(token) is not StoreToken or self._active != token:
            return None
        if self._generations.get(token.manager_index) != token.generation:
            return None
        if type(container_id) is not int or type(slot_id) is not int:
            return None
        if not 0 <= slot_id < SLOTS_PER_CONTAINER:
            return None
        if 0 <= container_id < LEGACY_COUNT:
            region = "LEGACY_ARRAY"
            offset = LEGACY_ARRAY_START + (
                container_id * SLOTS_PER_CONTAINER + slot_id
            ) * RECORD_SIZE
            if offset + RECORD_SIZE > LEGACY_CURSOR_START:
                return None
        elif container_id in WARDROBE_5_TO_8_IDS and simulate_extension is True:
            region = "SIMULATED_SIDECAR"
            offset = (
                (container_id - WARDROBE_5_TO_8_IDS[0]) * SLOTS_PER_CONTAINER
                + slot_id
            ) * RECORD_SIZE
            if offset + RECORD_SIZE > SIDECAR_BYTES_PER_STORE:
                return None
        else:
            return None
        return RecordRoute(region, offset, container_id, slot_id,
                           token.manager_index, token.generation)

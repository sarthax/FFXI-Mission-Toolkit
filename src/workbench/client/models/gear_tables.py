"""Python port of xi-model-viewer's GEAR_TABLES (D:\\Claude\\FFXI-Tools\\xi-model-viewer\\ui\\js\\dat\\modelids.js),
the real (Atom0s' common_geartables.php-derived) race -> slot -> file_id group tables.

CONFIRMED this session (2026-09-21) against a live Topaz-DSP DB + dat-extractor: the raw per-slot
value Topaz stores/sends in look_t (head/body/hands/legs/feet/main/sub/ranged) encodes as

    raw = slot_index * 4096 + model_id      (slot_index: head=1, body=2, hands=3, legs=4,
                                              feet=5, main=6, sub=7, ranged=8; 0 = unequipped)

and model_id plugs directly into this module's group-cumulative lookup to get a real file_id.
Verified end to end: Laiteconce (ElvaanFemale, npcid 16781339) head=4116 -> model_id=20 ->
file_id=16660 -> dat-extractor resolves ROM/42/41.DAT (a real file on disk). main=24576 ->
model_id=0 -> file_id=17920 -> ROM/43/65.DAT (also real). Do not re-derive this from scratch --
see docs/project-memory or mob_look_decode.py's docstring for the writeup.
"""

GEAR_SLOTS = ["face", "head", "body", "hands", "legs", "feet", "main", "sub", "ranged"]

# raw look_t slot value = slot_index*4096 + model_id. face has no slot index (not stored in look_t
# gear fields -- only in the separate `face` byte), so it is omitted here; order matches mmo.h's
# look_t layout: head, body, hands, legs, feet, main, sub, ranged.
SLOT_INDEX = {"head": 1, "body": 2, "hands": 3, "legs": 4, "feet": 5, "main": 6, "sub": 7, "ranged": 8}

RACE_SKELETON_RELS = {
    "HumeM": "ROM\\27\\82.DAT",
    "HumeF": "ROM\\32\\58.DAT",
    "ElvaanM": "ROM\\37\\31.DAT",
    "ElvaanF": "ROM\\42\\4.DAT",
    "Tarutaru": "ROM\\46\\93.DAT",
    "Mithra": "ROM\\51\\89.DAT",
    "Galka": "ROM\\56\\59.DAT",
}

GEAR_TABLE_RACE_TO_COMPOSER = {
    "HumeMale": "HumeM", "HumeFemale": "HumeF",
    "ElvaanMale": "ElvaanM", "ElvaanFemale": "ElvaanF",
    "TaruMale": "Tarutaru", "TaruFemale": "Tarutaru",
    "Mithra": "Mithra", "Galka": "Galka",
}

# {race: {slot: [[base_file_id, count], ...]}} -- verbatim from modelids.js.
GEAR_TABLES = {
    "HumeMale": {"face": [[7080, 32]], "head": [[7112, 256], [63323, 48], [63371, 16], [71247, 256], [98787, 32], [102961, 64]], "body": [[7368, 256], [63387, 48], [63435, 16], [71503, 256], [98819, 32], [103025, 64]], "hands": [[7624, 256], [63451, 48], [63499, 16], [71759, 256], [98851, 32], [103089, 64]], "legs": [[7880, 256], [63515, 48], [63563, 16], [72015, 256], [98883, 32], [103153, 64]], "feet": [[8136, 256], [63579, 48], [63627, 16], [72271, 256], [98915, 32], [103217, 64]], "main": [[8392, 512], [63643, 128], [72527, 256], [107301, 300], [0, 64]], "sub": [[41199, 512], [66459, 128], [81999, 256], [105201, 300], [0, 64]], "ranged": [[9416, 256]]},
    "HumeFemale": {"face": [[10256, 32]], "head": [[10288, 256], [63771, 48], [63819, 16], [72783, 256], [98947, 32], [103281, 64]], "body": [[10544, 256], [63835, 48], [63883, 16], [73039, 256], [98979, 32], [103345, 64]], "hands": [[10800, 256], [63899, 48], [63947, 16], [73295, 256], [99011, 32], [103409, 64]], "legs": [[11056, 256], [63963, 48], [64011, 16], [73551, 256], [99043, 32], [103473, 64]], "feet": [[11312, 256], [64027, 48], [64075, 16], [73807, 256], [99075, 32], [103537, 64]], "main": [[11568, 512], [64091, 128], [74063, 256], [107601, 300], [0, 64]], "sub": [[42479, 512], [66587, 128], [82255, 256], [105501, 300], [0, 64]], "ranged": [[12592, 256]]},
    "ElvaanMale": {"face": [[13432, 32]], "head": [[13464, 256], [64219, 48], [64267, 16], [74319, 256], [99107, 32], [103601, 64]], "body": [[13720, 256], [64283, 48], [64331, 16], [74575, 256], [99139, 32], [103665, 64]], "hands": [[13976, 256], [64347, 48], [64395, 16], [74831, 256], [99171, 32], [103729, 64]], "legs": [[14232, 256], [64411, 48], [64459, 16], [75087, 256], [99203, 32], [103793, 64]], "feet": [[14488, 256], [64475, 48], [64523, 16], [75343, 256], [99235, 32], [103857, 64]], "main": [[14744, 512], [64539, 128], [75599, 256], [107901, 300], [0, 64]], "sub": [[43759, 512], [66715, 128], [82511, 256], [105801, 300], [0, 64]], "ranged": [[15768, 256]]},
    "ElvaanFemale": {"face": [[16608, 32]], "head": [[16640, 256], [64667, 48], [64715, 16], [75855, 256], [99267, 32], [103921, 64]], "body": [[16896, 256], [64731, 48], [64779, 16], [76111, 256], [99299, 32], [103985, 64]], "hands": [[17152, 256], [64795, 48], [64843, 16], [76367, 256], [99331, 32], [104049, 64]], "legs": [[17408, 256], [64859, 48], [64907, 16], [76623, 256], [99363, 32], [104113, 64]], "feet": [[17664, 256], [64923, 48], [64971, 16], [76879, 256], [99395, 32], [104177, 64]], "main": [[17920, 512], [64987, 128], [77135, 256], [108201, 300], [0, 64]], "sub": [[45039, 512], [66843, 128], [82767, 256], [106101, 300], [0, 64]], "ranged": [[18944, 256]]},
    "TaruMale": {"face": [[19784, 32]], "head": [[19816, 256], [65115, 48], [65163, 16], [77391, 256], [99427, 32], [104241, 64]], "body": [[20072, 256], [65179, 48], [65227, 16], [77647, 256], [99459, 32], [104305, 64]], "hands": [[20328, 256], [65243, 48], [65291, 16], [77903, 256], [99491, 32], [104369, 64]], "legs": [[20584, 256], [65307, 48], [65355, 16], [78159, 256], [99523, 32], [104433, 64]], "feet": [[20840, 256], [65371, 48], [65419, 16], [78415, 256], [99555, 32], [104497, 64]], "main": [[21096, 512], [65435, 128], [78671, 256], [108501, 300], [0, 64]], "sub": [[46319, 512], [66971, 128], [83023, 256], [106401, 300], [0, 64]], "ranged": [[22120, 256]]},
    "TaruFemale": {"face": [[22952, 32]], "head": [[19816, 256], [65115, 48], [65171, 16], [77391, 256], [99443, 32], [104241, 64]], "body": [[20072, 256], [65179, 48], [65235, 16], [77647, 256], [99475, 32], [104305, 64]], "hands": [[20328, 256], [65243, 48], [65299, 16], [77903, 256], [99507, 32], [104369, 64]], "legs": [[20584, 256], [65307, 48], [65363, 16], [78159, 256], [99539, 32], [104433, 64]], "feet": [[20840, 256], [65371, 48], [65427, 16], [78415, 256], [99571, 32], [104497, 64]], "main": [[21096, 512], [65435, 128], [78671, 256], [108501, 300], [0, 64]], "sub": [[46319, 512], [66971, 128], [83023, 256], [106401, 300], [0, 64]], "ranged": [[22120, 256]]},
    "Mithra": {"face": [[23184, 32]], "head": [[23216, 256], [65563, 48], [65611, 16], [78927, 256], [99587, 32], [104561, 64]], "body": [[23472, 256], [65627, 48], [65675, 16], [79183, 256], [99619, 32], [104625, 64]], "hands": [[23728, 256], [65691, 48], [65739, 16], [79439, 256], [99651, 32], [104689, 64]], "legs": [[23984, 256], [65755, 48], [65803, 16], [79695, 256], [99683, 32], [104753, 64]], "feet": [[24240, 256], [65819, 48], [65867, 16], [79951, 256], [99715, 32], [104817, 64]], "main": [[24496, 512], [65883, 128], [80207, 256], [108801, 300], [0, 64]], "sub": [[47599, 512], [67099, 128], [83279, 256], [106701, 300], [0, 64]], "ranged": [[25520, 256]]},
    "Galka": {"face": [[26360, 32]], "head": [[26392, 256], [66011, 48], [66059, 16], [80463, 256], [99747, 32], [104881, 64]], "body": [[26648, 256], [66075, 48], [66123, 16], [80719, 256], [99779, 32], [104945, 64]], "hands": [[26904, 256], [66139, 48], [66187, 16], [80975, 256], [99811, 32], [105009, 64]], "legs": [[27160, 256], [66203, 48], [66251, 16], [81231, 256], [99843, 32], [105073, 64]], "feet": [[27416, 256], [66267, 48], [66315, 16], [81487, 256], [99875, 32], [105137, 64]], "main": [[27672, 512], [66331, 128], [81743, 256], [109101, 300], [0, 64]], "sub": [[48879, 512], [67227, 128], [83535, 256], [107001, 300], [0, 64]], "ranged": [[28696, 256]]},
}


def decode_slot_value(raw: int):
    """raw look_t slot value -> (slot_name, model_id), or None if unequipped (raw == 0).
    Raises ValueError if raw doesn't decode to a known slot (should not happen for real data)."""
    if raw == 0:
        return None
    slot_idx, model_id = divmod(raw, 4096)
    for name, idx in SLOT_INDEX.items():
        if idx == slot_idx:
            return name, model_id
    raise ValueError(f"raw slot value {raw} has unrecognized slot index {slot_idx}")


def model_id_to_file_id(race: str, slot: str, model_id: int):
    """(race, slot, cumulative model_id) -> real file_id, or None if out of range / a reserved
    zero-base group. race must be a GEAR_TABLES key (HumeMale, ElvaanFemale, ...)."""
    groups = GEAR_TABLES.get(race, {}).get(slot)
    if not groups:
        return None
    cursor = 0
    for base, count in groups:
        if cursor <= model_id < cursor + count:
            if base == 0:
                return None  # reserved/unused range
            return base + (model_id - cursor)
        cursor += count
    return None


def resolve_gear_file_ids(race: str, gear: dict) -> dict:
    """gear: {"head": raw, "body": raw, ...} (as decoded by mob_look_decode.decode_look_data).
    Returns {slot: {"model_id": int, "file_id": int|None}} for every equipped (nonzero) slot."""
    out = {}
    for slot, raw in gear.items():
        decoded = decode_slot_value(raw)
        if decoded is None:
            continue
        decoded_slot, model_id = decoded
        if decoded_slot != slot:
            # Sanity check -- the field name in `gear` should already match the slot the raw
            # value's own index encodes. A mismatch means the pattern broke for this row.
            out[slot] = {"model_id": model_id, "file_id": None,
                         "error": f"slot index in raw value ({decoded_slot}) != field name ({slot})"}
            continue
        out[slot] = {"model_id": model_id, "file_id": model_id_to_file_id(race, slot, model_id)}
    return out

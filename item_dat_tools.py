"""Client-side FFXI item DAT reader/writer -- vendored from vekien/xi-tools
(D:\\Claude\\xi-tools-vekien, src/xi/ui/items/{xi_layout,xi_parser}.py) and trimmed of its
click-CLI plumbing so mission_toolkit can call it as a plain library.

Why this exists: the server's item_equipment.level (etc.) is only an equip-permission
check. The FFXI client independently refuses to equip an item below the level its own
copy of ITEM.DAT says the item requires -- so a real "make this armor level 90" edit has
to patch both the server row (item_edit.py) and this binary record, or the two disagree
and the client silently blocks the equip. See docs/project-memory/04-technical-knowledge.md
and CLAUDE.md's ID rules -- this module is the "client needs to be edited too" half.

Cipher: every byte rotated left 3 bits. Record stride is detected per file (0xC00 legacy /
0x1400 retail-Sept-2026) -- never assumed. Verified field-by-field by xi-tools against
30,000+ real item records in both formats; ported here unchanged except for path resolution
(FFXI_DIR comes from mission_toolkit's settings.get_ffxi_install(), not a .env file) and
output (writes go straight back into FFXI_DIR, with a one-time .orig backup per DAT file --
see backup_dat_once()). Do not hand-tune offsets here; re-diff against xi-tools-vekien if a
future FFXI client update shifts them (that repo's docs/retail/*.md tracks layout changes).
"""
from __future__ import annotations

import os
import sqlite3
import struct
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import settings as settings_mod

# ── stride / format constants ────────────────────────────────────────────────
STRIDE_LEGACY = 0xC00    # 3072 -- every client before the 10 Sept 2026 update
STRIDE_RETAIL = 0x1400   # 5120 -- retail from 10 Sept 2026
STRIDES = (STRIDE_RETAIL, STRIDE_LEGACY)

FORMAT_LEGACY = 'legacy'
FORMAT_RETAIL = 'retail'
FORMAT_BY_STRIDE = {STRIDE_LEGACY: FORMAT_LEGACY, STRIDE_RETAIL: FORMAT_RETAIL}
STRIDE_BY_FORMAT = {v: k for k, v in FORMAT_BY_STRIDE.items()}

ICON_OFFSET = 0x280
ICON_DATA = ICON_OFFSET + 4
TERMINATOR = 0xFF

LAYOUTS = ('general', 'usable', 'puppet', 'armor', 'weapon', 'maze', 'instinct', 'roe')
TYPE_LAYOUT = {0: 'general', 1: 'usable', 3: 'armor', 4: 'weapon', 5: 'puppet', 6: 'maze'}
TYPE_NAME = {0: 'general', 1: 'consumable', 3: 'armor', 4: 'weapon', 5: 'puppet', 6: 'furnishing'}

_COMMON_LEGACY = {
    'id':          (0x00, '<I'),
    'flags':       (0x04, '<H'),
    'stack':       (0x06, '<H'),
    'type':        (0x08, '<H'),
    'resource_id': (0x0A, '<H'),
    'targets':     (0x0C, '<H'),
}
_COMMON_RETAIL = {
    'id':          (0x00, '<I'),
    'flags':       (0x04, '<H'),
    'stack':       (0x08, '<H'),
    'type':        (0x0A, '<H'),
    'resource_id': (0x0C, '<H'),
    'targets':     (0x0E, '<H'),
}
_EQUIP_LEGACY = {
    'level':          (0x0E, '<H'),
    'slots':          (0x10, '<H'),
    'races':          (0x12, '<H'),
    'jobs':           (0x14, '<I'),
    'superior_level': (0x18, '<H'),
}
_EQUIP_RETAIL = {
    'level':          (0x10, '<H'),
    'slots':          (0x12, '<H'),
    'races':          (0x14, '<H'),
    'jobs':           (0x18, '<I'),
    'superior_level': (0x1C, '<H'),
}

FIELDS: dict = {
    'general': {FORMAT_LEGACY: {**_COMMON_LEGACY}, FORMAT_RETAIL: {**_COMMON_RETAIL}},
    'usable': {
        FORMAT_LEGACY: {**_COMMON_LEGACY, 'cast_time': (0x0E, '<H')},
        FORMAT_RETAIL: {**_COMMON_RETAIL, 'cast_time': (0x10, '<H')},
    },
    'puppet': {
        FORMAT_LEGACY: {**_COMMON_LEGACY, 'puppet_slot': (0x0E, '<H'), 'element_charge': (0x10, '<I')},
        FORMAT_RETAIL: {**_COMMON_RETAIL, 'puppet_slot': (0x10, '<H'), 'element_charge': (0x14, '<I')},
    },
    'armor': {
        FORMAT_LEGACY: {
            **_COMMON_LEGACY, **_EQUIP_LEGACY,
            'shield_size': (0x1A, '<H'), 'max_charges': (0x1C, '<H'), 'cast_time': (0x1E, '<H'),
            'use_delay': (0x20, '<H'), 'reuse_delay': (0x22, '<H'), 'item_level': (0x26, '<H'),
        },
        FORMAT_RETAIL: {
            **_COMMON_RETAIL, **_EQUIP_RETAIL,
            'shield_size': (0x1E, '<H'), 'max_charges': (0x20, '<H'), 'cast_time': (0x22, '<H'),
            'use_delay': (0x24, '<H'), 'reuse_delay': (0x26, '<H'), 'item_level': (0x2A, '<H'),
        },
    },
    'weapon': {
        FORMAT_LEGACY: {
            **_COMMON_LEGACY, **_EQUIP_LEGACY,
            'dmg': (0x1C, '<H'), 'delay': (0x1E, '<H'), 'dps': (0x20, '<H'),
            'skill': (0x22, '<B'), 'jug_size': (0x23, '<B'),
            'max_charges': (0x28, '<H'), 'cast_time': (0x2A, '<H'), 'use_delay': (0x2C, '<H'),
            'reuse_delay': (0x2E, '<H'), 'base_item_id': (0x30, '<H'), 'item_level': (0x32, '<H'),
        },
        FORMAT_RETAIL: {
            **_COMMON_RETAIL, **_EQUIP_RETAIL,
            'dmg': (0x20, '<H'), 'delay': (0x22, '<H'), 'dps': (0x24, '<H'),
            'skill': (0x26, '<B'), 'jug_size': (0x27, '<B'),
            'max_charges': (0x2C, '<H'), 'cast_time': (0x2E, '<H'), 'use_delay': (0x30, '<H'),
            'reuse_delay': (0x32, '<H'), 'base_item_id': (0x34, '<H'), 'item_level': (0x36, '<H'),
        },
    },
    'maze': {FORMAT_LEGACY: {**_COMMON_LEGACY}, FORMAT_RETAIL: {**_COMMON_RETAIL}},
    'instinct': {
        FORMAT_LEGACY: {**_COMMON_LEGACY, 'level': (0x0E, '<H'), 'races': (0x12, '<H'), 'instinct_cost': (0x18, '<H')},
        FORMAT_RETAIL: {**_COMMON_RETAIL, 'level': (0x10, '<H'), 'races': (0x14, '<H'), 'instinct_cost': (0x1C, '<H')},
    },
    'roe': {FORMAT_LEGACY: {**_COMMON_LEGACY}, FORMAT_RETAIL: {**_COMMON_LEGACY}},
}

TEXT_OFFSETS: dict = {
    'general':  {FORMAT_LEGACY: 0x18, FORMAT_RETAIL: 0x1C},
    'usable':   {FORMAT_LEGACY: 0x1C, FORMAT_RETAIL: 0x1C},
    'puppet':   {FORMAT_LEGACY: 0x18, FORMAT_RETAIL: 0x1C},
    'armor':    {FORMAT_LEGACY: 0x2C, FORMAT_RETAIL: 0x30},
    'weapon':   {FORMAT_LEGACY: 0x38, FORMAT_RETAIL: 0x3C},
    'maze':     {FORMAT_LEGACY: 0x54, FORMAT_RETAIL: 0x54},
    'instinct': {FORMAT_LEGACY: 0x28, FORMAT_RETAIL: 0x2C},
    'roe':      {FORMAT_LEGACY: 0x20, FORMAT_RETAIL: 0x20},
}

JOBS = ['WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD', 'DRK', 'BST', 'BRD', 'RNG', 'SAM',
        'NIN', 'DRG', 'SMN', 'BLU', 'COR', 'PUP', 'DNC', 'SCH', 'GEO', 'RUN']

ITEM_FLAGS = {
    0x0001: 'rare', 0x0002: 'ex', 0x0004: 'usable', 0x0008: 'npc_only',
    0x0020: 'deliverable', 0x0040: 'bazaar', 0x0080: 'storage', 0x0200: 'scroll',
    0x0800: 'temporary', 0x4000: 'trial', 0x8000: 'enchanted',
}

# item_equipment.slot / item_dat_tools 'slots' bitmask -- bit index N = SLOT_N from
# C:\topaz\src\map\entities\battleentity.h SLOT_* enum (SLOT_MAIN=0x00 .. SLOT_BACK=0x0F,
# confirmed sequential 0-15 matching retail equip-slot order). Bitmask usage confirmed at
# charutils.cpp:2318 (`getEquipSlotId() & (1 << slotID)`).
SLOTS = ['main', 'sub', 'range', 'ammo', 'head', 'body', 'hands', 'legs', 'feet',
         'neck', 'waist', 'ear1', 'ear2', 'ring1', 'ring2', 'back']

# item_usable.validTargets bitmask -- TARGET_* enum, C:\topaz\src\map\entities\battleentity.h:361-369.
# Column is tinyint(2), so only the low byte (0x01-0x80) is reachable; TARGET_PET (0x100) does not fit.
VALID_TARGETS = {
    0x01: 'self', 0x02: 'player_party', 0x04: 'enemy', 0x08: 'player_alliance',
    0x10: 'player', 0x20: 'player_dead', 0x40: 'npc', 0x80: 'player_party_pianissimo',
}

# item_puppet.element -- NOT a flag bitmask. Confirmed at C:\topaz\src\map\utils\puppetutils.cpp
# (getElementSlots() >> (i*4)) & 0xF, used identically for frames/heads/attachments -- it's 8 packed
# 4-bit (0-15) element-capacity values, one nibble per element. Element order (0-7) confirmed against
# the contiguous EFFECT_FIRE_MANEUVER..EFFECT_DARK_MANEUVER run in status_effect.h (300-307) and its
# use at puppetutils.cpp:687 (`element = maneuver - EFFECT_FIRE_MANEUVER`).
ELEMENTS = ['fire', 'ice', 'wind', 'earth', 'thunder', 'water', 'light', 'dark']

# item_basic.aH -- which Auction House submenu the item appears under (0 = not sellable at AH).
# A single enum value, not a bitmask. Confirmed against the real AUCTION_CATEGORY-style enum
# used by Topaz/LSB-lineage servers (comment block supplied by the user, cross-checked against
# the numeric AH category ordering already visible in C:\topaz\sql\item_basic.sql's own aH values).
AH_CATEGORY = {
    0: 'none (not sellable at AH)', 1: 'h2h', 2: 'dagger', 3: 'sword', 4: 'greatsword',
    5: 'axe', 6: 'greataxe', 7: 'scythe', 8: 'polearm', 9: 'katana', 10: 'greatkatana',
    11: 'club', 12: 'staff', 13: 'bow', 14: 'instruments', 15: 'ammunition',
    16: 'shield', 17: 'head', 18: 'body', 19: 'hands', 20: 'legs', 21: 'feet',
    22: 'neck', 23: 'waist', 24: 'earrings', 25: 'rings', 26: 'back', 27: 'unused',
    28: 'white magic', 29: 'black magic', 30: 'summoning', 31: 'ninjutsu', 32: 'songs',
    33: 'medicines', 34: 'furnishings', 35: 'crystals', 36: 'cards', 37: 'cursed items',
    38: 'smithing', 39: 'goldsmithing', 40: 'clothcraft', 41: 'leathercraft', 42: 'bonecraft',
    43: 'woodworking', 44: 'alchemy', 45: 'geomancer', 46: 'misc', 47: 'fishing gear',
    48: 'pet items', 49: 'ninja tools', 50: 'beast-made', 51: 'fish', 52: 'meat & eggs',
    53: 'seafood', 54: 'vegetables', 55: 'soups', 56: 'breads & rice', 57: 'sweets',
    58: 'drinks', 59: 'ingredients', 60: 'dice', 61: 'automaton', 62: 'grips',
    63: 'alchemy 2', 64: 'misc 2', 65: 'misc 3',
}

# item_furnishing.moghancement -- a real keyitem-style ENUM value, NOT a bitmask: confirmed via
# C:\topaz\src\map\entities\charentity.cpp's UpdateMoghancement() (`switch (m_moghancementID)`,
# single-value equality) and CItemFurnishing::m_moghancement being a plain uint16 in
# item_furnishing.h. Only one moghancement can ever be active on a piece of furniture at a time,
# so this renders as a dropdown, not checkboxes, despite superficially looking bitmask-shaped.
MOGHANCEMENT = {
    0: 'none',
    512: 'fire (reduced material loss, fire synth)', 513: 'ice (reduced material loss, ice synth)',
    514: 'wind (reduced material loss, wind synth)', 515: 'earth (reduced material loss, earth synth)',
    516: 'lightning (reduced material loss, thunder synth)', 517: 'water (reduced material loss, water synth)',
    518: 'light (reduced material loss, light synth)', 519: 'dark (reduced material loss, dark synth)',
    520: 'experience (reduced exp loss on KO)', 521: 'gardening (reduced plant withering)',
    522: 'desynthesis (+1-2% desynth success)', 523: 'fishing (+1 fishing skill)',
    524: 'woodworking (+1 woodworking skill)', 525: 'smithing (+1 smithing skill)',
    526: 'goldsmithing (+1 goldsmithing skill)', 527: 'clothcraft (+1 clothcraft skill)',
    528: 'leathercraft (+1 leathercraft skill)', 529: 'bonecraft (+1 bonecraft skill)',
    530: 'alchemy (+1 alchemy skill)', 531: 'cooking (+1 cooking skill)',
    532: 'conquest (+individual conquest points)', 533: 'region (+region conquest points)',
    534: 'fishing item (+chance to find items fishing)',
    535: 'sandoria conquest (+individual CP, San dOrian only)',
    536: 'bastok conquest (+individual CP, Bastokan only)',
    537: 'windurst conquest (+individual CP, Windurstian only)',
    538: 'money (+10% gil dropped by monsters)', 539: 'campaign (+5% Allied Forces evaluation)',
    540: 'money II (+gil received)', 541: 'skill gains (+combat/magic skill gain rate)',
    542: 'bounty (+10% exp/capacity points)',
}

# item_mods.modId -- ground truth Mod enum, extracted directly (never hand-transcribed) from
# C:	opaz\src\map\modifier.h's own `enum class Mod` block (642 entries). This is the
# server's real modifier ID space; item_mods.value is the raw signed value applied for that mod
# (meaning varies per mod -- flat stat points, tenths/percent-of-1000, seconds, etc. per the
# comment on each entry below, copied verbatim from modifier.h). Cross-checked against
# landsandboat-reference/documentation/mods_by_id.txt (same LSB-lineage enum, confirms naming),
# but this dict is built from Topaz's own header, not the LSB copy, since Topaz is what's live.
MOD_NAMES = {
    0: "NONE -- Essential, but does nothing :)",
    1: "DEF -- Target's Defense",
    2: "HP -- Target's HP",
    3: "HPP -- HP Percentage",
    4: "CONVMPTOHP -- MP -> HP (Cassie Earring)",
    5: "MP -- MP +/-",
    6: "MPP -- MP Percentage",
    7: "CONVHPTOMP -- HP -> MP",
    8: "STR -- Strength",
    9: "DEX -- Dexterity",
    10: "VIT -- Vitality",
    11: "AGI -- Agility",
    12: "INT -- Intelligence",
    13: "MND -- Mind",
    14: "CHR -- Charisma",
    15: "FIREDEF -- Fire Defense",
    16: "ICEDEF -- Ice Defense",
    17: "WINDDEF -- Wind Defense",
    18: "EARTHDEF -- Earth Defense",
    19: "THUNDERDEF -- Thunder Defense",
    20: "WATERDEF -- Water Defense",
    21: "LIGHTDEF -- Light Defense",
    22: "DARKDEF -- Dark Defense",
    23: "ATT -- Attack",
    24: "RATT -- Ranged Attack",
    25: "ACC -- Accuracy",
    26: "RACC -- Ranged Accuracy",
    27: "ENMITY -- Enmity",
    28: "MATT -- Magic Attack",
    29: "MDEF -- Magic Defense",
    30: "MACC -- Magic Accuracy",
    31: "MEVA -- Magic Evasion",
    32: "FIREATT -- Fire Damage",
    33: "ICEATT -- Ice Damage",
    34: "WINDATT -- Wind Damage",
    35: "EARTHATT -- Earth Damage",
    36: "THUNDERATT -- Thunder Damage",
    37: "WATERATT -- Water Damage",
    38: "LIGHTATT -- Light Damage",
    39: "DARKATT -- Dark Damage",
    40: "FIREACC -- Fire Accuracy",
    41: "ICEACC -- Ice Accuracy",
    42: "WINDACC -- Wind Accuracy",
    43: "EARTHACC -- Earth Accuracy",
    44: "THUNDERACC -- Thunder Accuracy",
    45: "WATERACC -- Water Accuracy",
    46: "LIGHTACC -- Light Accuracy",
    47: "DARKACC -- Dark Accuracy",
    48: "WSACC -- Weaponskill Accuracy",
    49: "SLASHRES -- Slash Resistance",
    50: "PIERCERES -- Piercing Resistance",
    51: "IMPACTRES -- Impact Resistance",
    52: "HTHRES -- Hand-To-Hand Resistance",
    54: "FIRERES -- % Fire Resistance",
    55: "ICERES -- % Ice Resistance",
    56: "WINDRES -- % Wind Resistance",
    57: "EARTHRES -- % Earth Resistance",
    58: "THUNDERRES -- % Thunder Resistance",
    59: "WATERRES -- % Water Resistance",
    60: "LIGHTRES -- % Light Resistance",
    61: "DARKRES -- % Dark Resistance",
    62: "ATTP -- % Attack",
    63: "DEFP -- % Defense",
    64: "COMBAT_SKILLUP_RATE -- % increase in skillup combat rate",
    65: "MAGIC_SKILLUP_RATE -- % increase in skillup magic rate",
    66: "RATTP -- % Ranged Attack",
    67: "ENHANCES_CURSNA_RCVD -- Potency of 'Cursna' effects received",
    68: "EVA -- Evasion",
    69: "RDEF -- Ranged Defense",
    70: "REVA -- Ranged Evasion",
    71: "MPHEAL -- MP Recovered while healing",
    72: "HPHEAL -- HP Recovered while healing",
    73: "STORETP -- Increases the rate at which TP is gained",
    80: "HTH -- Hand To Hand Skill",
    81: "DAGGER -- Dagger Skill",
    82: "SWORD -- Sword Skill",
    83: "GSWORD -- Great Sword Skill",
    84: "AXE -- Axe Skill",
    85: "GAXE -- Great Axe Skill",
    86: "SCYTHE -- Scythe Skill",
    87: "POLEARM -- Polearm Skill",
    88: "KATANA -- Katana Skill",
    89: "GKATANA -- Great Katana Skill",
    90: "CLUB -- Club Skill",
    91: "STAFF -- Staff Skill",
    92: "RAMPART_DURATION -- Rampart duration in seconds",
    93: "FLEE_DURATION -- Flee duration in seconds",
    94: "MEDITATE_DURATION -- Meditate duration in seconds",
    95: "WARDING_CIRCLE_DURATION -- Warding Circle extended duration in seconds",
    96: "SOULEATER_EFFECT -- Souleater power in percents",
    97: "BOOST_EFFECT -- Boost power in tenths",
    98: "CAMOUFLAGE_DURATION -- Camouflage duration in percents",
    99: "FOOD_MACCP -- Macc% see https://www.bg-wiki.com/bg/Category:Magic_Accuracy_Food",
    100: "FOOD_MACC_CAP -- Sets Upper limit for FOOD_MACCP",
    101: "AUTO_MELEE_SKILL -- Automaton Melee Skill",
    102: "AUTO_RANGED_SKILL -- Automaton Range Skill",
    103: "AUTO_MAGIC_SKILL -- Automaton Magic Skill",
    104: "ARCHERY -- Archery Skill",
    105: "MARKSMAN -- Marksman Skill",
    106: "THROW -- Throw Skill",
    107: "GUARD -- Guard Skill",
    108: "EVASION -- Evasion Skill",
    109: "SHIELD -- Shield Skill",
    110: "PARRY -- Parry Skill",
    111: "DIVINE -- Divine Magic Skill",
    112: "HEALING -- Healing Magic Skill",
    113: "ENHANCE -- Enhancing Magic Skill",
    114: "ENFEEBLE -- Enfeebling Magic Skill",
    115: "ELEM -- Elemental Magic Skill",
    116: "DARK -- Dark Magic Skill",
    117: "SUMMONING -- Summoning Magic Skill",
    118: "NINJUTSU -- Ninjutsu Magic Skill",
    119: "SINGING -- Singing Magic Skill",
    120: "STRING -- String Magic Skill",
    121: "WIND -- Wind Magic Skill",
    122: "BLUE -- Blue Magic Skill",
    123: "CHAKRA_MULT -- Chakra multiplier increase (from gear)",
    124: "CHAKRA_REMOVAL -- Extra statuses removed by Chakra",
    125: "SUPPRESS_OVERLOAD -- Kenkonken 'Suppresses Overload' mod. Unclear how this works exactly. Requires testing on retail.",
    126: "BP_DAMAGE -- Blood Pact: Rage Damage increase percentage",
    127: "FISH -- Fishing Skill",
    128: "WOOD -- Woodworking Skill",
    129: "SMITH -- Smithing Skill",
    130: "GOLDSMITH -- Goldsmithing Skill",
    131: "CLOTH -- Clothcraft Skill",
    132: "LEATHER -- Leathercraft Skill",
    133: "BONE -- Bonecraft Skill",
    134: "ALCHEMY -- Alchemy Skill",
    135: "COOK -- Cooking Skill",
    136: "SYNERGY -- Synergy Skill",
    137: "RIDING -- Riding Skill",
    144: "ANTIHQ_WOOD -- Woodworking Success Rate %",
    145: "ANTIHQ_SMITH -- Smithing Success Rate %",
    146: "ANTIHQ_GOLDSMITH -- Goldsmithing Success Rate %",
    147: "ANTIHQ_CLOTH -- Clothcraft Success Rate %",
    148: "ANTIHQ_LEATHER -- Leathercraft Success Rate %",
    149: "ANTIHQ_BONE -- Bonecraft Success Rate %",
    150: "ANTIHQ_ALCHEMY -- Alchemy Success Rate %",
    151: "ANTIHQ_COOK -- Cooking Success Rate %",
    160: "DMG -- Damage Taken %",
    161: "DMGPHYS -- Physical Damage Taken %",
    162: "DMGBREATH -- Breath Damage Taken %",
    163: "DMGMAGIC -- Magic Damage Taken %",
    164: "DMGRANGE -- Range Damage Taken %",
    165: "CRITHITRATE -- Raises chance to crit",
    166: "ENEMYCRITRATE -- Raises chance enemy will crit",
    167: "HASTE_MAGIC -- Haste (and Slow) from magic - 10000 base, 375 = 3.75%",
    168: "SPELLINTERRUPT -- % Spell Interruption Rate",
    169: "MOVE -- % Movement Speed",
    170: "FASTCAST -- Increases Spell Cast Time (TRAIT)",
    171: "DELAY -- Increase/Decrease Delay",
    172: "RANGED_DELAY -- Increase/Decrease Ranged Delay",
    173: "MARTIAL_ARTS -- The integer amount of delay to reduce from H2H weapons' base delay. (TRAIT)",
    174: "SKILLCHAINBONUS -- Damage bonus applied to skill chain damage.  Modifier from effects/traits",
    175: "SKILLCHAINDMG -- Damage bonus applied to skill chain damage.  Modifier from gear (multiplicative after effect/traits)",
    176: "FOOD_HPP",
    177: "FOOD_HP_CAP",
    178: "FOOD_MPP",
    179: "FOOD_MP_CAP",
    180: "FOOD_ATTP",
    181: "FOOD_ATT_CAP",
    182: "FOOD_DEFP",
    183: "FOOD_DEF_CAP",
    184: "FOOD_ACCP",
    185: "FOOD_ACC_CAP",
    186: "FOOD_RATTP",
    187: "FOOD_RATT_CAP",
    188: "FOOD_RACCP",
    189: "FOOD_RACC_CAP",
    190: "DMGPHYS_II -- Physical Damage Taken II % (Burtgang)",
    191: "QUICK_DRAW_MACC -- Quick draw magic accuracy",
    224: "VERMIN_KILLER -- Enhances 'Vermin Killer' effect",
    225: "BIRD_KILLER -- Enhances 'Bird Killer' effect",
    226: "AMORPH_KILLER -- Enhances 'Amorph Killer' effect",
    227: "LIZARD_KILLER -- Enhances 'Lizard Killer' effect",
    228: "AQUAN_KILLER -- Enhances 'Aquan Killer' effect",
    229: "PLANTOID_KILLER -- Enhances 'Plantiod Killer' effect",
    230: "BEAST_KILLER -- Enhances 'Beast Killer' effect",
    231: "UNDEAD_KILLER -- Enhances 'Undead Killer' effect",
    232: "ARCANA_KILLER -- Enhances 'Arcana Killer' effect",
    233: "DRAGON_KILLER -- Enhances 'Dragon Killer' effect",
    234: "DEMON_KILLER -- Enhances 'Demon Killer' effect",
    235: "EMPTY_KILLER -- Enhances 'Empty Killer' effect",
    236: "HUMANOID_KILLER -- Enhances 'Humanoid Killer' effect",
    237: "LUMORIAN_KILLER -- Enhances 'Lumorian Killer' effect",
    238: "LUMINION_KILLER -- Enhances 'Luminion Killer' effect",
    240: "SLEEPRES -- Enhances 'Resist Sleep' effect",
    241: "POISONRES -- Enhances 'Resist Poison' effect",
    242: "PARALYZERES -- Enhances 'Resist Paralyze' effect",
    243: "BLINDRES -- Enhances 'Resist Blind' effect",
    244: "SILENCERES -- Enhances 'Resist Silence' effect",
    245: "VIRUSRES -- Enhances 'Resist Virus' effect",
    246: "PETRIFYRES -- Enhances 'Resist Petrify' effect",
    247: "BINDRES -- Enhances 'Resist Bind' effect",
    248: "CURSERES -- Enhances 'Resist Curse' effect",
    249: "GRAVITYRES -- Enhances 'Resist Gravity' effect",
    250: "SLOWRES -- Enhances 'Resist Slow' effect",
    251: "STUNRES -- Enhances 'Resist Stun' effect",
    252: "CHARMRES -- Enhances 'Resist Charm' effect",
    253: "AMNESIARES -- Enhances 'Resist Amnesia' effect",
    254: "LULLABYRES -- Enhances 'Resist Lullaby' effect",
    255: "DEATHRES -- Used by gear and ATMA that give resistance to instance KO",
    256: "AFTERMATH -- Aftermath ID",
    257: "PARALYZE -- Paralyze -- percent chance to proc",
    258: "MIJIN_RERAISE -- Augments Mijin Gakure",
    259: "DUAL_WIELD -- Percent reduction in dual wield delay.",
    260: "CURE_POTENCY_II -- % cure potency II | bonus from gear is capped at 30",
    288: "DOUBLE_ATTACK -- Percent chance to proc",
    289: "SUBTLE_BLOW -- How much TP to reduce.",
    290: "ENF_MAG_POTENCY -- Increases Enfeebling magic potency %",
    291: "COUNTER -- Percent chance to counter",
    292: "KICK_ATTACK_RATE -- Percent chance to kick",
    293: "AFFLATUS_SOLACE -- Pool of HP accumulated during Afflatus Solace",
    294: "AFFLATUS_MISERY -- Pool of HP accumulated during Afflatus Misery",
    295: "CLEAR_MIND -- Used in conjunction with HEALMP to increase amount between tics",
    296: "CONSERVE_MP -- Percent chance",
    297: "ENHANCES_SABOTEUR -- Increases Saboteur Potency %",
    298: "STEAL -- Increase/Decrease THF Steal chance",
    299: "BLINK -- Tracks blink shadows",
    300: "STONESKIN -- Tracks stoneskin HP pool",
    301: "PHALANX -- Tracks direct damage reduction",
    302: "TRIPLE_ATTACK -- Percent chance",
    303: "TREASURE_HUNTER -- Percent chance",
    304: "TAME -- Additional percent chance to charm",
    305: "RECYCLE -- Percent chance to recycle",
    306: "ZANSHIN -- Zanshin percent chance",
    307: "UTSUSEMI -- Everyone's favorite --tracks shadows.",
    308: "NINJA_TOOL -- Percent chance to not use a tool.",
    309: "BLUE_POINTS -- Tracks extra blue points",
    310: "ENHANCES_CURSNA -- Used by gear with the 'Enhances Cursna' or 'Cursna+' attribute",
    311: "MAGIC_DAMAGE -- Magic damage added directly to the spell's base damage",
    312: "SCAVENGE_EFFECT",
    313: "DIA_DOT -- Increases the DoT damage of Dia",
    314: "SHARPSHOT",
    315: "ENH_DRAIN_ASPIR -- % damage boost to Drain and Aspir",
    316: "DMG_REFLECT -- Tracks totals",
    317: "ROLL_ROGUES -- Tracks totals",
    318: "ROLL_GALLANTS -- Tracks totals",
    319: "ROLL_CHAOS -- Tracks totals",
    320: "ROLL_BEAST -- Tracks totals",
    321: "ROLL_CHORAL -- Tracks totals",
    322: "ROLL_HUNTERS -- Tracks totals",
    323: "ROLL_SAMURAI -- Tracks totals",
    324: "ROLL_NINJA -- Tracks totals",
    325: "ROLL_DRACHEN -- Tracks totals",
    326: "ROLL_EVOKERS -- Tracks totals",
    327: "ROLL_MAGUS -- Tracks totals",
    328: "ROLL_CORSAIRS -- Tracks totals",
    329: "ROLL_PUPPET -- Tracks totals",
    330: "ROLL_DANCERS -- Tracks totals",
    331: "ROLL_SCHOLARS -- Tracks totals",
    332: "BUST -- # of busts",
    333: "FINISHING_MOVES -- Tracks # of finishing moves",
    334: "LIGHT_ARTS_EFFECT",
    335: "DARK_ARTS_EFFECT",
    336: "LIGHT_ARTS_SKILL",
    337: "DARK_ARTS_SKILL",
    338: "LIGHT_ARTS_REGEN -- Regen bonus flat HP amount from Light Arts and Tabula Rasa",
    339: "REGEN_DURATION",
    340: "WIDESCAN",
    341: "ENSPELL -- stores the type of enspell active (0 if nothing)",
    342: "SPIKES -- store the type of spike spell active (0 if nothing)",
    343: "ENSPELL_DMG -- stores the base damage of the enspell before reductions",
    344: "SPIKES_DMG -- stores the base damage of the spikes before reductions",
    345: "TP_BONUS",
    346: "PERPETUATION_REDUCTION -- stores the MP/tick reduction from gear",
    347: "FIRE_AFFINITY_DMG -- They're stored separately due to Magian stuff - they can grant different levels of",
    348: "ICE_AFFINITY_DMG -- the damage/acc/perp affinity on the same weapon, so they must be separated.",
    349: "WIND_AFFINITY_DMG -- Each level of damage affinity is +/-5% damage, acc is +/-10 acc, and perp is",
    350: "EARTH_AFFINITY_DMG -- +/-1 mp/tic. This means that anyone adding these modifiers will have to add",
    351: "THUNDER_AFFINITY_DMG -- 1 to the wiki amount. For example, Fire Staff has 2 in fire affinity for",
    352: "WATER_AFFINITY_DMG -- DMG, ACC, and PERP, while the wiki lists it as having 1 in each.",
    353: "LIGHT_AFFINITY_DMG",
    354: "DARK_AFFINITY_DMG",
    355: "ADDS_WEAPONSKILL",
    356: "ADDS_WEAPONSKILL_DYN -- In Dynamis",
    357: "BP_DELAY -- stores blood pact delay reduction",
    358: "STEALTH",
    359: "RAPID_SHOT -- Percent chance to proc rapid shot",
    360: "CHARM_TIME -- extends the charm time only, no effect of charm chance",
    361: "JUMP_TP_BONUS -- bonus tp player receives when using jump (must be divided by 10)",
    362: "JUMP_ATT_BONUS -- ATT% bonus for jump + high jump",
    363: "HIGH_JUMP_ENMITY_REDUCTION -- for gear that reduces more enmity from high jump",
    364: "REWARD_HP_BONUS -- Percent to add to reward HP healed. (364)",
    365: "SNAP_SHOT -- Percent reduction to range attack delay",
    366: "MAIN_DMG_RATING -- adds damage rating to main hand weapon (maneater/blau dolch etc hidden effects)",
    367: "SUB_DMG_RATING -- adds damage rating to off hand weapon",
    368: "REGAIN -- auto regain TP (from items) | this is multiplied by 10 e.g. 20 is 2% TP",
    369: "REFRESH -- auto refresh from equipment",
    370: "REGEN -- auto regen from equipment",
    371: "AVATAR_PERPETUATION -- stores base cost of current avatar",
    372: "WEATHER_REDUCTION -- stores perpetuation reduction depending on weather",
    373: "DAY_REDUCTION -- stores perpetuation reduction depending on day",
    374: "CURE_POTENCY -- % cure potency | bonus from gear is capped at 50",
    375: "CURE_POTENCY_RCVD -- % potency of received cure | healer's roll, some items have this",
    376: "RANGED_DMG_RATING -- adds damage rating to ranged weapon",
    377: "MAIN_DMG_RANK -- adds weapon rank to main weapon http://wiki.bluegartr.com/bg/Weapon_Rank",
    378: "SUB_DMG_RANK -- adds weapon rank to sub weapon",
    379: "RANGED_DMG_RANK -- adds weapon rank to ranged weapon",
    380: "DELAYP -- delay addition percent (does not affect tp gain)",
    381: "RANGED_DELAYP -- ranged delay addition percent (does not affect tp gain)",
    382: "EXP_BONUS",
    383: "HASTE_ABILITY -- Haste (and Slow) from abilities - 10000 base, 375 = 3.75%",
    384: "HASTE_GEAR -- Haste (and Slow) from equipment - 10000 base, 375 = 3.75%",
    385: "SHIELD_BASH",
    386: "KICK_DMG -- increases kick attack damage",
    387: "UDMGPHYS -- Uncapped Damage Multipliers",
    388: "UDMGBREATH -- Used in sentinal, invincible, physical shield etc",
    389: "UDMGMAGIC",
    390: "UDMGRANGE",
    391: "CHARM_CHANCE -- extra chance to charm (light+apollo staff ect)",
    392: "WEAPON_BASH",
    393: "BLACK_MAGIC_COST -- MP cost for black magic (light/dark arts)",
    394: "WHITE_MAGIC_COST -- MP cost for white magic (light/dark arts)",
    395: "BLACK_MAGIC_CAST -- Cast time for black magic (light/dark arts)",
    396: "WHITE_MAGIC_CAST -- Cast time for black magic (light/dark arts)",
    397: "BLACK_MAGIC_RECAST -- Recast time for black magic (light/dark arts)",
    398: "WHITE_MAGIC_RECAST -- Recast time for white magic (light/dark arts)",
    399: "ALACRITY_CELERITY_EFFECT -- Bonus for celerity/alacrity effect",
    400: "STORMSURGE_EFFECT",
    401: "SUBLIMATION_BONUS",
    402: "WYVERN_BREATH",
    403: "STEP_ACCURACY -- Bonus accuracy for Dancer's steps",
    404: "REGEN_DOWN -- poison",
    405: "REFRESH_DOWN -- plague, reduce mp",
    406: "REGAIN_DOWN -- plague, reduce tp",
    407: "UFASTCAST -- uncapped fast cast",
    408: "DA_DOUBLE_DAMAGE -- Double attack's double damage chance %.",
    409: "TA_TRIPLE_DAMAGE -- Triple attack's triple damage chance %.",
    410: "ZANSHIN_DOUBLE_DAMAGE -- Zanshin's double damage chance %.",
    411: "QUICK_DRAW_DMG -- Flat damage increase to base QD damage",
    412: "EAT_RAW_FISH",
    413: "EAT_RAW_MEAT",
    414: "RETALIATION -- Increases damage of Retaliation hits",
    415: "SAMBA_DOUBLE_DAMAGE -- Double damage chance when samba is up.",
    416: "NULL_PHYSICAL_DAMAGE -- Occasionally annuls damage from physical attacks, in percents",
    417: "QUICK_DRAW_TRIPLE_DAMAGE -- Chance to do triple damage with quick draw.",
    418: "BAR_ELEMENT_NULL_CHANCE -- Bar Elemental spells will occasionally NULLify damage of the same element.",
    419: "GRIMOIRE_INSTANT_CAST -- Spells that match your current Arts will occasionally cast instantly, without recast.",
    420: "BARRAGE_ACC -- Barrage accuracy",
    421: "CRIT_DMG_INCREASE -- Raises the damage of critical hit by percent %",
    422: "DOUBLE_SHOT_RATE -- The rate that double shot can proc. Without this, the default is 40%.",
    423: "VELOCITY_SNAPSHOT_BONUS -- Increases Snapshot whilst Velocity Shot is up.",
    424: "VELOCITY_RATT_BONUS -- Increases Ranged Attack whilst Velocity Shot is up.",
    425: "SHADOW_BIND_EXT -- Extends the time of shadowbind",
    426: "ABSORB_PHYSDMG_TO_MP -- Absorbs a percentage of physical damage taken to MP.",
    427: "ENMITY_LOSS_REDUCTION -- Reduces Enmity lost when taking damage",
    428: "PERFECT_COUNTER_ATT -- TODO: Raises weapon damage by 20 when countering while under the Perfect Counter effect. This also affects Weapon Rank (though",
    429: "FOOTWORK_ATT_BONUS -- Raises the attack bonus of Footwork. (Tantra Gaiters +2 raise 25/256 to 38/256)",
    430: "QUAD_ATTACK -- Quadruple attack chance.",
    431: "ADDITIONAL_EFFECT",
    432: "ENSPELL_DMG_BONUS",
    433: "MINNE_EFFECT",
    434: "MINUET_EFFECT",
    435: "PAEON_EFFECT",
    436: "REQUIEM_EFFECT",
    437: "THRENODY_EFFECT",
    438: "MADRIGAL_EFFECT",
    439: "MAMBO_EFFECT",
    440: "LULLABY_EFFECT",
    441: "ETUDE_EFFECT",
    442: "BALLAD_EFFECT",
    443: "MARCH_EFFECT",
    444: "FINALE_EFFECT",
    445: "CAROL_EFFECT",
    446: "MAZURKA_EFFECT",
    447: "ELEGY_EFFECT",
    448: "PRELUDE_EFFECT",
    449: "HYMNUS_EFFECT",
    450: "VIRELAI_EFFECT",
    451: "SCHERZO_EFFECT",
    452: "ALL_SONGS_EFFECT",
    453: "MAXIMUM_SONGS_BONUS",
    454: "SONG_DURATION_BONUS",
    455: "SONG_SPELLCASTING_TIME",
    456: "RERAISE_I -- Reraise.",
    457: "RERAISE_II -- Reraise II.",
    458: "RERAISE_III -- Reraise III.",
    459: "FIRE_ABSORB -- Occasionally absorbs fire elemental damage, in percents",
    460: "ICE_ABSORB -- Occasionally absorbs ice elemental damage, in percents",
    461: "WIND_ABSORB -- Occasionally absorbs wind elemental damage, in percents",
    462: "EARTH_ABSORB -- Occasionally absorbs earth elemental damage, in percents",
    463: "LTNG_ABSORB -- Occasionally absorbs thunder elemental damage, in percents",
    464: "WATER_ABSORB -- Occasionally absorbs water elemental damage, in percents",
    465: "LIGHT_ABSORB -- Occasionally absorbs light elemental damage, in percents",
    466: "DARK_ABSORB -- Occasionally absorbs dark elemental damage, in percents",
    467: "FIRE_NULL",
    468: "ICE_NULL",
    469: "WIND_NULL",
    470: "EARTH_NULL",
    471: "LTNG_NULL",
    472: "WATER_NULL",
    473: "LIGHT_NULL",
    474: "DARK_NULL",
    475: "MAGIC_ABSORB -- Occasionally absorbs magic damage taken, in percents",
    476: "MAGIC_NULL -- Occasionally annuls magic damage taken, in percents",
    477: "HELIX_DURATION",
    478: "HELIX_EFFECT",
    479: "RAPID_SHOT_DOUBLE_DAMAGE -- Rapid shot's double damage chance %.",
    480: "ABSORB_DMG_CHANCE -- Chance to absorb damage %",
    481: "EXTRA_DUAL_WIELD_ATTACK -- Chance to land an extra attack when dual wielding",
    482: "EXTRA_KICK_ATTACK -- Occasionally allows a second Kick Attack during an attack round without the use of Footwork.",
    483: "WARCRY_DURATION -- Warcy duration bonus from gear",
    484: "AUSPICE_EFFECT -- Bonus to Auspice Subtle Blow Effect.",
    485: "SHIELD_MASTERY_TP -- Shield mastery TP bonus when blocking with a shield",
    486: "TACTICAL_PARRY -- Tactical Parry Tp Bonus",
    487: "MAG_BURST_BONUS -- Magic Burst Bonus Modifier (percent)",
    488: "INHIBIT_TP -- Inhibits TP Gain (percent)",
    489: "GRIMOIRE_SPELLCASTING -- 'Grimoire: Reduces spellcasting time' bonus",
    490: "SAMBA_DURATION -- Samba duration bonus",
    491: "WALTZ_POTENTCY -- Waltz Potentcy Bonus",
    492: "JIG_DURATION -- Jig duration bonus in percents",
    493: "VFLOURISH_MACC -- Violent Flourish accuracy bonus",
    494: "STEP_FINISH -- Bonus finishing moves from steps",
    495: "ENHANCES_HOLYWATER -- Used by gear with the 'Enhances Holy Water' or 'Holy Water+' attribute",
    496: "GOV_CLEARS -- 4% bonus per Grounds of Valor Page clear",
    497: "WALTZ_DELAY -- Waltz Ability Delay modifier (-1 mod is -1 second)",
    498: "SAMBA_PDURATION -- Samba percent duration bonus",
    499: "ITEM_SPIKES_TYPE -- Type spikes an item has",
    500: "ITEM_SPIKES_DMG -- Damage of an items spikes",
    501: "ITEM_SPIKES_CHANCE -- Chance of an items spike proc",
    503: "FERAL_HOWL_DURATION -- +20% duration per merit when wearing augmented Monster Jackcoat +2",
    504: "MANEUVER_BONUS -- Maneuver Stat Bonus",
    505: "OVERLOAD_THRESH -- Overload Threshold Bonus",
    506: "EXTRA_DMG_CHANCE -- Proc rate of OCC_DO_EXTRA_DMG. 111 would be 11.1%",
    507: "OCC_DO_EXTRA_DMG -- Multiplier for 'Occasionally do x times normal damage'. 250 would be 2.5 times damage.",
    508: "THIRD_EYE_COUNTER_RATE -- Adds counter to 3rd eye anticipates & if using Seigan counter rate is increased by 15%",
    509: "CLAMMING_IMPROVED_RESULTS",
    510: "CLAMMING_REDUCED_INCIDENTS",
    511: "CHOCOBO_RIDING_TIME -- Increases chocobo riding time",
    512: "PHYS_ABSORB -- Occasionally absorbs physical damage taken, in percents",
    513: "HARVESTING_RESULT -- Improves harvesting results",
    514: "LOGGING_RESULT -- Improves logging results",
    515: "MINING_RESULT -- Improves mining results",
    516: "ABSORB_DMG_TO_MP -- Unlike PLD gear mod, works on all damage types (Ethereal Earring)",
    517: "EGGHELM",
    518: "SHIELDBLOCKRATE -- Affects shield block rate, percent based",
    519: "CURE_CAST_TIME -- cure cast time reduction",
    520: "TRICK_ATK_AGI -- % AGI boost to Trick Attack (if gear mod, needs to be equipped on hit)",
    521: "AUGMENTS_ABSORB -- Direct Absorb spell increase while Liberator is equipped (percentage based)",
    522: "NIN_NUKE_BONUS -- magic attack bonus for NIN nukes",
    523: "AMMO_SWING -- Extra swing rate w/ ammo (ie. Jailer weapons). Use gearsets, and does nothing for non-players.",
    524: "AOE_NA -- Set to 1 to make -na spells/erase always AoE w/ Divine Veil",
    525: "AUGMENTS_CONVERT -- Convert HP to MP Ratio Multiplier. Value = MP multiplier rate.",
    526: "AUGMENTS_SA -- Adds Critical Attack Bonus to Sneak Attack, percentage based.",
    527: "AUGMENTS_TA -- Adds Critical Attack Bonus to Trick Attack, percentage based.",
    528: "ROLL_RANGE -- Additional range for COR roll abilities.",
    529: "ENHANCES_REFRESH -- 'Enhances Refresh' adds +1 per modifier to spell's tick result.",
    530: "NO_SPELL_MP_DEPLETION -- % to not deplete MP on spellcast.",
    531: "FORCE_FIRE_DWBONUS -- Set to above 0 to force fire day/weather spell bonus/penalty.",
    532: "FORCE_ICE_DWBONUS -- Set to above 0 to force ice day/weather spell bonus/penalty.",
    533: "FORCE_WIND_DWBONUS -- Set to above 0 to force wind day/weather spell bonus/penalty.",
    534: "FORCE_EARTH_DWBONUS -- Set to above 0 to force earth day/weather spell bonus/penalty.",
    535: "FORCE_LIGHTNING_DWBONUS -- Set to above 0 to force lightning day/weather spell bonus/penalty.",
    536: "FORCE_WATER_DWBONUS -- Set to above 0 to force water day/weather spell bonus/penalty.",
    537: "FORCE_LIGHT_DWBONUS -- Set to above 0 to force light day/weather spell bonus/penalty.",
    538: "FORCE_DARK_DWBONUS -- Set to above 0 to force dark day/weather spell bonus/penalty.",
    539: "STONESKIN_BONUS_HP -- Bonus 'HP' granted to Stoneskin spell.",
    540: "ENHANCES_ELEMENTAL_SIPHON -- Bonus Base MP added to Elemental Siphon skill.",
    541: "BP_DELAY_II -- Blood Pact Delay Reduction II",
    542: "JOB_BONUS_CHANCE -- Chance to apply job bonus to COR roll without having the job in the party.",
    543: "COUNTERSTANCE_EFFECT -- Counterstance effect in percents",
    544: "FIRE_AFFINITY_ACC",
    545: "ICE_AFFINITY_ACC",
    546: "WIND_AFFINITY_ACC",
    547: "EARTH_AFFINITY_ACC",
    548: "THUNDER_AFFINITY_ACC",
    549: "WATER_AFFINITY_ACC",
    550: "LIGHT_AFFINITY_ACC",
    551: "DARK_AFFINITY_ACC",
    552: "DODGE_EFFECT -- Dodge effect in percents",
    553: "FIRE_AFFINITY_PERP",
    554: "ICE_AFFINITY_PERP",
    555: "WIND_AFFINITY_PERP",
    556: "EARTH_AFFINITY_PERP",
    557: "THUNDER_AFFINITY_PERP",
    558: "WATER_AFFINITY_PERP",
    559: "LIGHT_AFFINITY_PERP",
    560: "DARK_AFFINITY_PERP",
    561: "FOCUS_EFFECT -- Focus effect in percents",
    562: "MAGIC_CRITHITRATE -- Raises chance to magic crit",
    563: "MAGIC_CRIT_DMG_INCREASE -- Raises damage done when criting with magic",
    564: "JUG_LEVEL_RANGE -- Decreases the level range of spawned jug pets. Maxes out at 2.",
    565: "DAY_NUKE_BONUS -- Bonus damage from 'Elemental magic affected by day' (Sorc. Tonban)",
    566: "IRIDESCENCE -- Iridescence trait (additional weather damage/penalty)",
    567: "BARSPELL_AMOUNT -- Additional elemental resistance granted by bar- spells",
    568: "RAPTURE_AMOUNT -- Bonus amount added to Rapture effect",
    569: "EBULLIENCE_AMOUNT -- Bonus amount added to Ebullience effect",
    570: "WEAPONSKILL_DAMAGE_BASE",
    826: "AMMO_SWING_TYPE -- For the handedness of the weapon - 1h (1) vs. 2h/h2h (2). h2h can safely use the same function as 2h.",
    827: "BARSPELL_MDEF_BONUS -- Extra magic defense bonus granted to the bar- spell effect",
    828: "FORCE_JUMP_CRIT -- Critical hit rate bonus for jump and high jump",
    829: "WYVERN_EFFECTIVE_BREATH -- Increases the threshold for triggering healing breath/offensive breath more inclined to pick elemental weakness",
    831: "DMGMAGIC_II -- Magic Damage Taken II % (Aegis)",
    832: "AQUAVEIL_COUNT -- Modifies the amount of hits that Aquaveil absorbs before being removed",
    833: "SONG_RECAST_DELAY -- Reduces song recast time in seconds.",
    834: "QUICK_DRAW_DMG_PERCENT -- Percentage increase to QD damage",
    835: "MUG_EFFECT -- Mug effect as multiplier",
    836: "REVERSE_FLOURISH_EFFECT -- Reverse Flourish effect in tenths of squared term multiplier",
    837: "SENTINEL_EFFECT -- Sentinel effect in percents",
    838: "REGEN_MULTIPLIER -- Multiplier to base regen rate",
    839: "THIRD_EYE_ANTICIPATE_RATE -- Adds anticipate rate in percents",
    840: "ALL_WSDMG_ALL_HITS -- Generic (all Weaponskills) damage, on all hits.",
    841: "ALL_WSDMG_FIRST_HIT -- Generic (all Weaponskills) damage, first hit only.",
    842: "AUTO_DECISION_DELAY -- Reduces the Automaton's global decision delay",
    843: "AUTO_SHIELD_BASH_DELAY -- Reduces the Automaton's global shield bash delay",
    844: "AUTO_MAGIC_DELAY -- Reduces the Automaton's global magic delay",
    845: "AUTO_HEALING_DELAY -- Reduces the Automaton's global healing delay",
    846: "AUTO_HEALING_THRESHOLD -- Increases the healing trigger threshold",
    847: "BURDEN_DECAY -- Increases amount of burden removed per tick",
    848: "AUTO_SHIELD_BASH_SLOW -- Adds a slow effect to Shield Bash",
    849: "AUTO_TP_EFFICIENCY -- Causes the Automaton to wait to form a skillchain when its master is > 90% TP",
    850: "AUTO_SCAN_RESISTS -- Causes the Automaton to scan a target's resistances",
    851: "SYNTH_SUCCESS -- Rate of synthesis success",
    852: "SYNTH_SKILL_GAIN -- Synthesis skill gain rate",
    853: "REPAIR_EFFECT -- Removes # of status effects from the Automaton",
    854: "REPAIR_POTENCY -- Note: Only affects amount regenerated by a %, not the instant restore!",
    855: "PREVENT_OVERLOAD -- Overloading erases a water maneuver (except on water overloads) instead, if there is one",
    856: "ENSPELL_CHANCE -- Chance of enspell activating (0 = 100%, 10 = 10%, 30 = 30%, ...)",
    857: "HOLY_CIRCLE_DURATION -- Holy Circle extended duration in seconds",
    858: "ARCANE_CIRCLE_DURATION -- Arcane Circle extended duration in seconds",
    859: "ANCIENT_CIRCLE_DURATION -- Ancient Circle extended duration in seconds",
    860: "CURE2MP_PERCENT -- Converts % of 'Cure' amount to MP",
    861: "SYNTH_FAIL_RATE -- Synthesis failure rate (percent)",
    862: "SYNTH_HQ_RATE -- High-quality success rate (not a percent)",
    863: "REM_OCC_DO_DOUBLE_DMG -- Proc rate for REM Aftermaths that apply 'Occasionally do double damage'",
    864: "REM_OCC_DO_TRIPLE_DMG -- Proc rate for REM Aftermaths that apply 'Occasionally do triple damage'",
    865: "MYTHIC_OCC_ATT_TWICE -- Proc rate for 'Occasionally attacks twice'",
    866: "MYTHIC_OCC_ATT_THRICE -- Proc rate for 'Occasionally attacks thrice'",
    867: "REM_OCC_DO_DOUBLE_DMG_RANGED -- Ranged attack specific",
    868: "REM_OCC_DO_TRIPLE_DMG_RANGED -- Ranged attack specific",
    869: "ROLL_BOLTERS -- Tracks totals",
    870: "ROLL_CASTERS -- Tracks totals",
    871: "ROLL_COURSERS -- Tracks totals",
    872: "ROLL_BLITZERS -- Tracks totals",
    873: "ROLL_TACTICIANS -- Tracks totals",
    874: "SNEAK_ATK_DEX -- % DEX boost to Sneak Attack (if gear mod, needs to be equipped on hit)",
    875: "ROLL_MISERS -- Tracks totals",
    876: "ROLL_COMPANIONS -- Tracks totals",
    877: "ROLL_AVENGERS -- Tracks totals",
    878: "ROLL_NATURALISTS -- Tracks totals",
    879: "ROLL_RUNEISTS -- Tracks totals",
    880: "SAVETP -- SAVETP Effect for Miser's Roll / ATMA / Hagakure.",
    881: "PHANTOM_ROLL -- Phantom Roll+ Effect from SOA Rings.",
    882: "PHANTOM_DURATION -- Phantom Roll Duration +.",
    883: "PERFECT_DODGE -- Increases Perfect Dodge duration in seconds",
    884: "ACC_COLLAB_EFFECT -- Increases amount of enmity transferred for Accomplice/Collaborator",
    885: "HIDE_DURATION -- Hide duration increase (percentage based)",
    886: "AUGMENTS_ASSASSINS_CHARGE -- Gives Assassin's Charge +1% Critical Hit Rate per merit level",
    887: "AUGMENTS_AMBUSH -- Gives +1% Triple Attack per merit level when Ambush conditions are met",
    889: "AUGMENTS_AURA_STEAL -- 20% chance of 2 effects to be dispelled or stolen per merit level",
    890: "ENH_MAGIC_DURATION -- Enhancing Magic Duration increase %",
    891: "ENHANCES_COURSERS_ROLL -- Courser's Roll Bonus % chance",
    892: "ENHANCES_CASTERS_ROLL -- Caster's Roll Bonus % chance",
    893: "ENHANCES_BLITZERS_ROLL -- Blitzer's Roll Bonus % chance",
    894: "ENHANCES_ALLIES_ROLL -- Allies' Roll Bonus % chance",
    895: "ENHANCES_TACTICIANS_ROLL -- Tactician's Roll Bonus % chance",
    896: "DESPOIL -- Increases THF Despoil chance",
    897: "GILFINDER -- Gilfinder, duh",
    898: "SMITE -- Raises attack when using H2H or 2H weapons (256 scale)",
    899: "TACTICAL_GUARD -- Tp increase when guarding",
    900: "UTSUSEMI_BONUS -- Extra shadows from gear",
    901: "ELEMENTAL_CELERITY -- Quickens Elemental Magic Casting",
    902: "OCCULT_ACUMEN -- Grants bonus TP when dealing damage with elemental or dark magic",
    903: "FENCER_TP_BONUS -- TP Bonus to weapon skills from Fencer Trait",
    904: "FENCER_CRITHITRATE -- Increased Crit chance from Fencer Trait",
    905: "SHIELD_DEF_BONUS -- Shield Defense Bonus",
    906: "DESPERATE_BLOWS -- Adds ability haste to Last Resort",
    907: "STALWART_SOUL -- Reduces damage taken from Souleater",
    908: "CRIT_DEF_BONUS -- Reduces crit hit damage",
    909: "QUICK_MAGIC -- Percent chance spells cast instantly (also reduces recast to 0, similar to Chainspell)",
    910: "DIVINE_BENISON -- Adds fast cast and enmity reduction to -Na spells (includes Erase). Enmity reduction is half of the fast cast amount",
    911: "DAKEN -- chance to throw a shuriken without consuming it",
    912: "AUGMENTS_CONSPIRATOR -- Applies Conspirator benefits to player at the top of the hate list",
    913: "BLOOD_BOON -- Occasionally cuts down MP cost of Blood Pact abilities. Does not affect abilities that require Astral Flow.",
    914: "EXPERIENCE_RETAINED -- Experience points retained upon death (this is a percentage)",
    915: "CAPACITY_BONUS -- Capacity point bonus granted",
    916: "DESYNTH_SUCCESS -- Rate of desynthesis success",
    917: "SYNTH_FAIL_RATE_FIRE -- Amount synthesis failure rate is reduced when using a fire crystal",
    918: "SYNTH_FAIL_RATE_ICE -- Amount synthesis failure rate is reduced when using a ice crystal",
    919: "SYNTH_FAIL_RATE_WIND -- Amount synthesis failure rate is reduced when using a wind crystal",
    920: "SYNTH_FAIL_RATE_EARTH -- Amount synthesis failure rate is reduced when using a earth crystal",
    921: "SYNTH_FAIL_RATE_LIGHTNING -- Amount synthesis failure rate is reduced when using a lightning crystal",
    922: "SYNTH_FAIL_RATE_WATER -- Amount synthesis failure rate is reduced when using a water crystal",
    923: "SYNTH_FAIL_RATE_LIGHT -- Amount synthesis failure rate is reduced when using a light crystal",
    924: "SYNTH_FAIL_RATE_DARK -- Amount synthesis failure rate is reduced when using a dark crystal",
    925: "SYNTH_FAIL_RATE_WOOD -- Amount synthesis failure rate is reduced when doing woodworking",
    926: "SYNTH_FAIL_RATE_SMITH -- Amount synthesis failure rate is reduced when doing smithing",
    927: "SYNTH_FAIL_RATE_GOLDSMITH -- Amount synthesis failure rate is reduced when doing goldsmithing",
    928: "SYNTH_FAIL_RATE_CLOTH -- Amount synthesis failure rate is reduced when doing clothcraft",
    929: "SYNTH_FAIL_RATE_LEATHER -- Amount synthesis failure rate is reduced when doing leathercraft",
    930: "SYNTH_FAIL_RATE_BONE -- Amount synthesis failure rate is reduced when doing bonecraft",
    931: "SYNTH_FAIL_RATE_ALCHEMY -- Amount synthesis failure rate is reduced when doing alchemy",
    932: "SYNTH_FAIL_RATE_COOK -- Amount synthesis failure rate is reduced when doing cooking",
    933: "CONQUEST_BONUS -- Conquest points bonus granted (percentage)",
    934: "CONQUEST_REGION_BONUS -- Increases the influence points awarded to the player's nation when receiving conquest points",
    935: "CAMPAIGN_BONUS -- Increases the evaluation for allied forces by percentage",
    937: "FOOD_DURATION -- Percentage to increase food duration",
    938: "AUTO_STEAM_JACKET -- Causes the Automaton to mitigate damage from successive attacks of the same type",
    939: "AUTO_STEAM_JACKED_REDUCTION -- Amount of damage reduced with Steam Jacket",
    940: "AUTO_SCHURZEN -- Prevents fatal damage leaving the automaton at 1HP and consumes an Earth manuever",
    941: "AUTO_EQUALIZER -- Reduces damage received according to damage taken",
    942: "AUTO_PERFORMANCE_BOOST -- Increases the performance of other attachments by a percentage",
    943: "AUTO_ANALYZER -- Causes the Automaton to mitigate damage from a special attack a number of times",
    944: "CONSERVE_TP -- Conserve TP trait, random chance between 10 and 200 TP",
    945: "BLUE_LEARN_CHANCE -- Additional chance to learn blue magic",
    946: "SNEAK_DURATION -- Additional duration in seconds",
    947: "INVISIBLE_DURATION -- Additional duration in seconds",
    948: "BERSERK_EFFECT -- Conqueror Berserk Effect",
    949: "WS_NO_DEPLETE -- % chance a Weaponskill depletes no TP.",
    954: "BERSERK_DURATION -- Berserk Duration",
    955: "AGGRESSOR_DURATION -- Aggressor Duration",
    956: "DEFENDER_DURATION -- Defender Duration",
    957: "WS_DEX_BONUS -- % bonus to dex_wsc.",
    958: "STATUSRES -- 'Resistance to All Status Ailments'",
    959: "CARDINAL_CHANT",
    960: "INDI_DURATION",
    961: "GEOMANCY",
    962: "WIDENED_COMPASS",
    963: "INQUARTATA -- increases parry rate by a flat %.",
    964: "RANGED_CRIT_DMG_INCREASE -- Increases ranged critical damage by a percent",
    965: "COVER_TO_MP -- Converts a successful cover's phsyical damage to MP",
    966: "COVER_MAGIC_AND_RANGED -- Redirects ranged and single target magic attacks to the cover ability user",
    967: "COVER_DURATION -- Increases Cover Duration",
    968: "MENDING_HALATION",
    969: "RADIAL_ARCANA",
    970: "CURATIVE_RECANTATION",
    971: "PRIMEVAL_ZEAL",
    972: "MOUNT_MOVE -- % Mount Movement Speed",
    973: "SUBTLE_BLOW_II -- Subtle Blow II Effect (Cap 50%) Total Effect (SB + SB_II cap 75%)",
    974: "WYVERN_SUBJOB_TRAITS -- Adds subjob traits to wyvern on spawn",
    975: "GARDENING_WILT_BONUS -- Increases the number of Vanadays a plant can survive before it wilts",
    976: "GUARD_PERCENT -- Guard Percent",
    978: "MAX_SWINGS -- Max swings for 'Occasionally attacks X times'",
    979: "ADDITIONAL_SWING_CHANCE -- Chance that allows for an additional swing despite of multiple hits, mostly for Amood weapons",
    980: "WS_STR_BONUS -- % bonus to str_wsc.",
    981: "WS_VIT_BONUS -- % bonus to vit_wsc.",
    982: "WS_AGI_BONUS -- % bonus to agi_wsc.",
    983: "WS_INT_BONUS -- % bonus to int_wsc.",
    984: "WS_MND_BONUS -- % bonus to mnd_wsc.",
    985: "WS_CHR_BONUS -- % bonus to chr_wsc.",
    986: "WYVERN_BREATH_MACC -- Increases accuracy of wyvern's breath. adds 10 magic accuracy per merit to the trait Strafe",
}

# item_usable.animation -- the visual effect id played on item use (potions, echo drops, etc.).
# NOT documented in Topaz C++ source with named constants (itemutils.cpp just forwards the raw
# smallint to the client via the item-use packet), so this list is sourced from
# landsandboat-reference/documentation/item_animations.txt (an LSB community reference of
# observed animation ids) rather than a Topaz enum -- treat entries as community-documented,
# not confirmed against Topaz's own source, and leave unlisted values as a plain number.
ITEM_ANIMATION = {
    6: 'remove disease', 7: 'remove curse',
    10: 'chr up', 24: 'agi up', 25: 'dex up', 26: 'int up', 27: 'mnd up', 28: 'str up', 29: 'vit up',
    30: 'potion', 31: 'hi potion', 32: 'ether', 33: 'hi ether', 34: 'elixir',
    55: 'item pop (e.g. toolbag)',
    64: 'erase', 65: 'erase (purple)', 66: 'high erase', 67: 'tp remove',
    68: 'poison', 69: 'paralyze', 70: 'blind', 71: 'silence', 72: 'sleep', 73: 'petrify',
    74: 'diseased', 75: 'curse', 76: 'exp ring', 77: 'exp ring (purple?)', 78: 'sparkles',
    79: 'teleport', 80: 'warp', 81: 'reraise', 82: 'round circle thing',
    91: 'healing / remedy', 92: 'remove effect',
    105: 'corsair',
}

# item_mods_pet.petType -- ground truth PetModType enum, extracted directly from
# C:\topaz\src\map\modifier.h's `enum class PetModType` block (8 entries). item_mods_pet.modId
# uses the SAME Mod enum as item_mods (see MOD_NAMES above) -- confirmed via itemutils.cpp's
# item_mods_pet load query, which casts column 1 to `Mod` and column 3 to `PetModType` and calls
# CItemEquipment::addPetModifier(CPetModifier(modID, petType, value)). petType=0 (All) means the
# mod applies to every pet type; other values scope it to one job's pet.
PET_TYPE_NAMES = {
    0: 'All',
    1: 'Avatar',
    2: 'Wyvern',
    3: 'Automaton',
    4: 'Harlequin',
    5: 'Valoredge',
    6: 'Sharpshot',
    7: 'Stormwaker',
}

# item_latents.latentId -- ground truth LATENT enum, extracted directly from
# C:\topaz\src\map\latent_effect.h's `enum class LATENT` (61 slots, ids 0-60, a few gaps left
# "free to use" per the header's own comments -- 33 is unused between WINDSDAY/ICEDAY, same for
# any id missing below). item_latents.modId uses the SAME Mod enum as item_mods (see MOD_NAMES),
# and item_latents.value is that mod's magnitude -- confirmed via itemutils.cpp's item_latents
# load query casting column 1 to Mod and column 3 to LATENT, then calling
# CItemEquipment::addLatent(latentId, latentParam, modID, value). latentParam's meaning is
# condition-specific (HP%, job id, zone id, etc, per the comment on each LATENT entry below,
# copied verbatim from latent_effect.h) -- shown as a plain number since it has no single enum.
LATENT_NAMES = {
    0: 'HP_UNDER_PERCENT -- hp less than or equal to % (param: hp percent)',
    1: 'HP_OVER_PERCENT -- hp more than % (param: hp percent)',
    2: 'HP_UNDER_TP_UNDER_100 -- hp less than or equal to %, tp under 100 (param: hp percent)',
    3: 'HP_OVER_TP_UNDER_100 -- hp more than %, tp over 100 (param: hp percent)',
    4: 'MP_UNDER_PERCENT -- mp less than or equal to % (param: mp percent)',
    5: 'MP_UNDER -- mp less than # (param: mp value)',
    6: 'TP_UNDER -- tp under # and during WS (param: tp value)',
    7: 'TP_OVER -- tp over # (param: tp value)',
    8: 'SUBJOB -- subjob (param: jobtype)',
    9: 'PET_ID -- pet type (param: pet id)',
    10: 'WEAPON_DRAWN -- weapon drawn',
    11: 'WEAPON_SHEATHED -- weapon sheathed',
    12: 'SIGNET_BONUS -- in conquest region, engaged to even match or less',
    13: 'STATUS_EFFECT_ACTIVE -- status effect on player (param: effect id)',
    14: 'NO_FOOD_ACTIVE -- no food effects active on player',
    15: 'PARTY_MEMBERS -- party size # (param: # of members)',
    16: 'PARTY_MEMBERS_IN_ZONE -- party size # and members in zone (param: # of members)',
    17: 'SANCTION_REGEN_BONUS -- in besieged region, hp less than param%',
    18: 'SANCTION_REFRESH_BONUS -- in besieged region, mp less than param%',
    19: 'SIGIL_REGEN_BONUS -- in campaign region, hp less than param%',
    20: 'SIGIL_REFRESH_BONUS -- in campaign region, mp less than param%',
    21: 'AVATAR_IN_PARTY -- party has specific avatar (param: pets.lua id, 21=any avatar)',
    22: 'JOB_IN_PARTY -- party has job (param: jobtype)',
    23: 'ZONE -- in zone (param: zoneid)',
    24: 'SYNTH_TRAINEE -- synth skill under 40 and no support',
    25: 'SONG_ROLL_ACTIVE -- any song or roll active',
    26: 'TIME_OF_DAY -- param: 0 daytime, 1 nighttime, 2 dusk-dawn',
    27: 'HOUR_OF_DAY -- param: 1 new day, 2 dawn, 3 day, 4 dusk, 5 evening, 6 dead of night',
    28: 'FIRESDAY',
    29: 'EARTHSDAY',
    30: 'WATERSDAY',
    31: 'WINDSDAY',
    32: 'DARKSDAY',
    34: 'ICEDAY',
    35: 'LIGHTNINGSDAY',
    36: 'LIGHTSDAY',
    37: 'MOON_PHASE -- param: 0 new, 1 waxing crescent, 2 first quarter, 3 waxing gibbous, 4 full, 5 waning gibbous, 6 last quarter, 7 waning crescent',
    38: 'JOB_MULTIPLE -- param: 0 odd, 2 even, 3-X divisor',
    39: 'JOB_MULTIPLE_AT_NIGHT -- param: 0 odd, 2 even, 3-X divisor',
    43: 'WEAPON_DRAWN_HP_UNDER -- param: hp percent',
    45: 'MP_UNDER_VISIBLE_GEAR -- mp <= %, from visible gear MP bonuses only',
    46: 'HP_OVER_VISIBLE_GEAR -- hp >= %, from visible gear HP bonuses only',
    47: 'WEAPON_BROKEN',
    48: 'IN_DYNAMIS',
    49: 'FOOD_ACTIVE -- food effect active (param: food itemid)',
    50: 'JOB_LEVEL_BELOW -- param: level',
    51: 'JOB_LEVEL_ABOVE -- param: level',
    52: 'WEATHER_ELEMENT -- param: 0 none,1 fire,2 ice,3 wind,4 earth,5 thunder,6 water,7 light,8 dark',
    53: 'NATION_CONTROL -- param: 0 under own nation control, 1 outside it',
    54: 'ZONE_HOME_NATION -- in zone and citizen of that nation (e.g. aketons)',
    55: 'MP_OVER -- mp greater than # (param: mp value)',
    56: 'WEAPON_DRAWN_MP_OVER -- weapon drawn and mp greater than # (param: mp value)',
    57: 'ELEVEN_ROLL_ACTIVE -- corsair roll of 11 active',
    58: 'IN_ASSAULT -- in an instance battle in a TOAU zone',
    59: 'VS_ECOSYSTEM -- vs specific ecosystem id',
    60: 'VS_FAMILY -- vs specific family id',
}

# (name, base_id, item_type, en_rom_path, jp_rom_path)
ITEM_DATS = [
    ('Items_1',       0,     0, 'ROM/118/106.DAT', 'ROM/0/4.DAT'),
    ('Consumable',    4096,  1, 'ROM/118/107.DAT', 'ROM/0/5.DAT'),
    ('Puppet',        8192,  5, 'ROM/118/110.DAT', 'ROM/0/8.DAT'),
    ('Items_2',       8704,  0, 'ROM/301/115.DAT', 'ROM/301/114.DAT'),
    ('Armor_1',       10240, 3, 'ROM/118/109.DAT', 'ROM/0/7.DAT'),
    ('Weapons',       16384, 4, 'ROM/118/108.DAT', 'ROM/0/6.DAT'),
    ('Armor_2',       23040, 3, 'ROM/286/73.DAT',  'ROM/286/72.DAT'),
    ('Moblin',        28672, 6, 'ROM/217/21.DAT',  'ROM/217/20.DAT'),
    ('Monstrosity_1', 29696, 0, 'ROM/288/80.DAT',  'ROM/288/79.DAT'),
    ('Items_7',       30720, 0, 'ROM/387/14.DAT',  'ROM/387/13.DAT'),
    ('RoE_Objectives',57344, 0, 'ROM/307/16.DAT',  'ROM/307/15.DAT'),
    ('Items_3',       61432, 0, 'ROM/314/89.DAT',  'ROM/314/89.DAT'),
    ('Monstrosity_2', 61440, 0, 'ROM/288/67.DAT',  'ROM/288/66.DAT'),
    ('RoE_Categories',61952, 0, 'ROM/307/24.DAT',  'ROM/307/23.DAT'),
    ('Items_4',       62976, 0, 'ROM/320/26.DAT',  'ROM/320/26.DAT'),
    ('Items_5',       63008, 0, 'ROM/332/49.DAT',  'ROM/332/47.DAT'),
    ('Items_6',       63024, 0, 'ROM/332/48.DAT',  'ROM/332/46.DAT'),
    ('Gil',           65535, 0, 'ROM/174/48.DAT',  'ROM/0/9.DAT'),
]

_DECRYPT = bytes(((b >> 5) | (b << 3)) & 0xFF for b in range(256))
_ENCRYPT = bytes(((b >> 3) | (b << 5)) & 0xFF for b in range(256))


def _decrypt(data: bytes) -> bytes:
    return bytes(data).translate(_DECRYPT)


def _encrypt(data: bytes) -> bytes:
    return bytes(data).translate(_ENCRYPT)


def ffxi_dir() -> str:
    d = settings_mod.get_ffxi_install()
    if not d:
        raise ValueError("FFXI install path isn't configured -- set it on the Settings page first")
    return str(d)


def dat_path(rom_path: str) -> Path:
    """Always the LIVE install's copy of a ROM-relative DAT path -- used for reads (browsing,
    comparison) and as the vanilla source for a pivot DAT's first edit. Never the write target
    in pivot mode -- see dat_write_dest()."""
    return Path(ffxi_dir()) / Path(rom_path.replace('/', '\\'))


def dat_target() -> str:
    """Whether client-DAT edits go to the live FFXI install ("live", default) or a separate
    Xi-Pivot overlay folder ("pivot") that never touches the real install -- see pivot_root()."""
    con = sqlite3.connect(str(settings_mod.DB_PATH))
    try:
        v = settings_mod.get(con, "item_dat_target")
    finally:
        con.close()
    return v if v in ("live", "pivot") else "live"


def set_dat_target(target: str):
    if target not in ("live", "pivot"):
        raise ValueError('target must be "live" or "pivot"')
    con = sqlite3.connect(str(settings_mod.DB_PATH))
    try:
        settings_mod.set_many(con, {"item_dat_target": target})
    finally:
        con.close()


def pivot_root() -> Path:
    """Xi-Pivot output folder -- a standalone overlay tree, mirroring the same ROM/x/y.DAT
    layout as the live install, meant for a Windower/Ashita-style DAT-overlay loader to point at
    so edited items load over an untouched retail install. Settings' xi_pivot_root if set, else a
    bundled default under this toolkit's own data/ folder."""
    con = sqlite3.connect(str(settings_mod.DB_PATH))
    try:
        v = settings_mod.get(con, "xi_pivot_root")
    finally:
        con.close()
    return Path(v) if v else Path(__file__).parent / 'data' / 'Xi-Pivot'


def pivot_dat_path(rom_path: str) -> Path:
    return pivot_root() / Path(rom_path.replace('/', '\\'))


def dat_write_source(rom_path: str) -> Path:
    """Which copy to base an edit's record data off. In pivot mode, an existing pivot copy (so
    successive pivot edits to the same DAT stack on each other) wins over the live install; the
    live install is only read as the vanilla base for a DAT's very first pivot edit."""
    if dat_target() == 'pivot':
        piv = pivot_dat_path(rom_path)
        if piv.exists():
            return piv
    return dat_path(rom_path)


def dat_write_dest(rom_path: str) -> Path:
    """Where an edit actually gets written -- the live install in "live" mode, or the Xi-Pivot
    folder (never the live install) in "pivot" mode."""
    return pivot_dat_path(rom_path) if dat_target() == 'pivot' else dat_path(rom_path)


def layout_for_type(item_type: int) -> str:
    return TYPE_LAYOUT.get(item_type, 'general')


def fields_for(layout: str, fmt: str) -> dict:
    return FIELDS.get(layout, FIELDS['general'])[fmt]


def text_offset(layout: str, fmt: str) -> int:
    return TEXT_OFFSETS.get(layout, TEXT_OFFSETS['general'])[fmt]


def text_offset_for(item_type: int, fmt: str) -> int:
    return text_offset(layout_for_type(item_type), fmt)


def read_field(rec: bytes, layout: str, fmt: str, name: str, default: int = 0) -> int:
    spec = fields_for(layout, fmt).get(name)
    if spec is None:
        return default
    off, sfmt = spec
    if off + struct.calcsize(sfmt) > len(rec):
        return default
    return struct.unpack_from(sfmt, rec, off)[0]


def write_field(rec: bytearray, layout: str, fmt: str, name: str, value: int) -> bool:
    spec = fields_for(layout, fmt).get(name)
    if spec is None:
        return False
    off, sfmt = spec
    size = struct.calcsize(sfmt)
    mask = (1 << (8 * size)) - 1
    struct.pack_into(sfmt, rec, off, int(value) & mask)
    if name == 'flags' and fmt == FORMAT_RETAIL:
        struct.pack_into('<H', rec, off + 2, 0)
    return True


def decode_flags(flags: int) -> list:
    return [name for bit, name in ITEM_FLAGS.items() if flags & bit]


def encode_flags(decoded: list) -> int:
    name_to_bit = {name: bit for bit, name in ITEM_FLAGS.items()}
    result = 0
    for name in decoded:
        if name in name_to_bit:
            result |= name_to_bit[name]
    return result


def decode_jobs(jobs: int) -> list:
    return [JOBS[i] for i in range(len(JOBS)) if jobs & (1 << i)]


def encode_jobs(jobs_list: list) -> int:
    job_to_bit = {job: (1 << i) for i, job in enumerate(JOBS)}
    result = 0
    for job in jobs_list:
        if job.upper() in job_to_bit:
            result |= job_to_bit[job.upper()]
    return result


def decode_slots(mask: int) -> list:
    return [SLOTS[i] for i in range(len(SLOTS)) if mask & (1 << i)]


def encode_slots(names: list) -> int:
    name_to_bit = {name: (1 << i) for i, name in enumerate(SLOTS)}
    result = 0
    for name in names:
        if name.lower() in name_to_bit:
            result |= name_to_bit[name.lower()]
    return result


def decode_element_slots(mask: int) -> dict:
    """{element_name: capacity 0-15}, per the packed-nibble layout confirmed in puppetutils.cpp."""
    return {ELEMENTS[i]: (mask >> (i * 4)) & 0xF for i in range(len(ELEMENTS))}


def encode_element_slots(values: dict) -> int:
    result = 0
    for i, name in enumerate(ELEMENTS):
        v = int(values.get(name, 0)) & 0xF
        result |= v << (i * 4)
    return result


def string_block_valid(rec: bytes, off: int) -> bool:
    if off < 0 or off + 8 > len(rec):
        return False
    n = struct.unpack_from('<I', rec, off)[0]
    if not 1 <= n <= 16:
        return False
    first = struct.unpack_from('<I', rec, off + 4)[0]
    return first == 4 + n * 8 and off + first < min(len(rec), ICON_OFFSET)


def find_text_offset(rec: bytes, expected: Optional[int] = None) -> Optional[int]:
    if expected is not None and string_block_valid(rec, expected):
        return expected
    for off in range(0x08, 0x92, 2):
        if string_block_valid(rec, off):
            return off
    return None


def _terminator_ratio(data: bytes, stride: int) -> float:
    count = len(data) // stride
    if not count:
        return 0.0
    hits = sum(1 for i in range(stride - 1, len(data), stride) if data[i] == TERMINATOR)
    return hits / count


def _ids_sequential(data: bytes, stride: int, probe: int = 8) -> bool:
    count = min(probe, len(data) // stride)
    if count < 2:
        return False
    ids = []
    for k in range(count):
        raw = data[k * stride:k * stride + 4]
        dec = bytes(((b >> 5) | (b << 3)) & 0xFF for b in raw)
        ids.append(struct.unpack('<I', dec)[0])
    return all(ids[k + 1] == ids[k] + 1 for k in range(count - 1))


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def detect_stride(data: bytes) -> int:
    n = len(data)
    cands = [s for s in STRIDES if n >= s and n % s == 0]
    if len(cands) == 1:
        return cands[0]
    if not cands:
        raise ValueError(f'not an item DAT: {n} bytes is not a multiple of 0xC00 or 0x1400')
    scored = sorted(((_terminator_ratio(data, s), s) for s in cands), reverse=True)
    if scored[0][0] > 0 and scored[0][0] > scored[1][0]:
        return scored[0][1]
    for s in cands:
        if _ids_sequential(data, s):
            return s
    return STRIDE_LEGACY


def detect_stride_path(path) -> int:
    p = Path(path)
    n = p.stat().st_size
    cands = [s for s in STRIDES if n >= s and n % s == 0]
    if len(cands) == 1:
        return cands[0]
    if not cands:
        raise ValueError(f'not an item DAT: {p} ({n} bytes)')
    lcm = STRIDE_RETAIL * STRIDE_LEGACY // _gcd(STRIDE_RETAIL, STRIDE_LEGACY)
    want = min(n, lcm * 8)
    with open(p, 'rb') as fh:
        head = fh.read(want)
    return detect_stride(head)


def format_for_stride(stride: int) -> str:
    try:
        return FORMAT_BY_STRIDE[stride]
    except KeyError:
        raise ValueError(f'unknown item record stride {stride:#x}') from None


def describe(stride: int) -> str:
    fmt = FORMAT_BY_STRIDE.get(stride)
    if fmt == FORMAT_RETAIL:
        return 'retail (0x1400-byte records, Sept 2026 layout)'
    if fmt == FORMAT_LEGACY:
        return 'legacy (0xC00-byte records)'
    return f'unknown ({stride:#x}-byte records)'


@dataclass
class ItemDat:
    path: Path
    data: bytearray
    stride: int

    @classmethod
    def load(cls, path) -> 'ItemDat':
        p = Path(path)
        raw = p.read_bytes()
        stride = detect_stride(raw)
        return cls(path=p, data=bytearray(_decrypt(raw)), stride=stride)

    @property
    def format(self) -> str:
        return format_for_stride(self.stride)

    @property
    def count(self) -> int:
        return len(self.data) // self.stride

    def record(self, idx: int) -> bytes:
        return bytes(self.data[idx * self.stride:(idx + 1) * self.stride])

    def set_record(self, idx: int, rec: bytes) -> None:
        if len(rec) != self.stride:
            raise ValueError(f'record is {len(rec)} bytes; this DAT uses {self.stride:#x}-byte records')
        self.data[idx * self.stride:(idx + 1) * self.stride] = rec

    def encrypted(self) -> bytes:
        return _encrypt(bytes(self.data))

    @property
    def icon_capacity(self) -> int:
        return self.stride - ICON_DATA - 1


def record_count(path) -> int:
    p = Path(path)
    return p.stat().st_size // detect_stride_path(p)


def _read_strings(rec: bytes, text_off: int) -> list:
    base = rec[text_off:]
    if len(base) < 4:
        return []
    n = struct.unpack_from('<I', base, 0)[0]
    if n == 0 or n > 16:
        return []
    if 4 + n * 8 > len(base):
        return []
    results = []
    for j in range(n):
        str_off = struct.unpack_from('<I', base, 4 + j * 8)[0]
        str_type = struct.unpack_from('<I', base, 4 + j * 8 + 4)[0]
        if str_type == 0:
            p = str_off + 0x1C
            if p >= len(base):
                results.append('')
                continue
            end = base.find(b'\x00', p)
            raw = base[p:end] if end != -1 else base[p:]
            try:
                results.append(raw.decode('cp932'))
            except Exception:
                results.append(raw.decode('latin-1', 'replace'))
        else:
            results.append('')
    return results


def _write_strings(strings: list, text_off: int, rec: bytearray) -> None:
    n = len(strings)
    struct.pack_into('<I', rec, text_off, n)
    cursor = 4 + n * 8
    for i, s in enumerate(strings):
        pos = text_off + cursor
        if isinstance(s, str):
            encoded = s.encode('cp932') + b'\x00'
            obj_len = (0x1C + len(encoded) + 3) & ~3
            if pos + obj_len > ICON_OFFSET:
                raise ValueError('item text does not fit before the icon at 0x280')
            rec[pos:pos + obj_len] = b'\x00' * obj_len
            struct.pack_into('<I', rec, pos, 1)
            rec[pos + 0x1C:pos + 0x1C + len(encoded)] = encoded
            flag = 0
        else:
            obj_len = 4
            if pos + obj_len > ICON_OFFSET:
                raise ValueError('item text does not fit before the icon at 0x280')
            struct.pack_into('<I', rec, pos, int(s or 0) & 0xFFFFFFFF)
            flag = 1
        struct.pack_into('<I', rec, text_off + 4 + i * 8, cursor)
        struct.pack_into('<I', rec, text_off + 4 + i * 8 + 4, flag)
        cursor += obj_len


def _resolve_text_offset(rec: bytes, item_type: int, fmt: str) -> Optional[int]:
    return find_text_offset(rec, text_offset_for(item_type, fmt))


@dataclass
class ItemRecord:
    id: int
    type: int
    type_name: str
    flags: int
    stack: int = 1
    resource_id: int = 0
    targets: int = 0
    name: str = ''
    singular: str = ''
    plural: str = ''
    description: str = ''
    name_jp: str = ''
    description_jp: str = ''
    level: int = 0
    slots: int = 0
    races: int = 0
    jobs: int = 0
    superior_level: int = 0
    kind: int = 0
    dmg: int = 0
    delay: int = 0
    dps: int = 0
    skill: int = 0
    icon_size: int = 0
    icon_data: bytes = field(default_factory=bytes, repr=False)
    dat: str = ''
    dat_ui: str = ''
    format: str = FORMAT_LEGACY
    record_index: int = 0
    category: str = ''


def _parse_record(item_id: int, rec_en: bytes, rec_jp: Optional[bytes], item_type: int,
                   dat_path_str: str, dat_ui: str = '', fmt: Optional[str] = None,
                   record_index: int = 0, category: str = '') -> Optional[ItemRecord]:
    if fmt is None:
        fmt = format_for_stride(len(rec_en))
    layout = layout_for_type(item_type)

    text_off = _resolve_text_offset(rec_en, item_type, fmt)
    if text_off is None:
        return None
    en = _read_strings(rec_en, text_off)
    if not en or not en[0] or en[0] == '.':
        return None

    jp = []
    if rec_jp:
        jp_off = _resolve_text_offset(rec_jp, item_type, format_for_stride(len(rec_jp)))
        if jp_off is not None:
            jp = _read_strings(rec_jp, jp_off)

    rf = lambda name: read_field(rec_en, layout, fmt, name)

    item = ItemRecord(
        id=item_id, type=item_type, type_name=TYPE_NAME.get(item_type, str(item_type)),
        flags=rf('flags'), stack=rf('stack'), resource_id=rf('resource_id'), targets=rf('targets'),
        name=en[0] if len(en) > 0 else '',
        singular=en[2] if len(en) > 2 else '',
        plural=en[3] if len(en) > 3 else '',
        description=en[4] if len(en) > 4 else '',
        name_jp=jp[0] if len(jp) > 0 else '',
        description_jp=jp[1] if len(jp) > 1 else '',
        dat=dat_path_str, dat_ui=dat_ui, format=fmt, record_index=record_index, category=category,
    )
    if item_type in (3, 4):
        item.level = rf('level')
        item.slots = rf('slots')
        item.races = rf('races')
        item.jobs = rf('jobs')
        item.superior_level = rf('superior_level')
    if item_type == 4:
        item.kind = rf('type')
        item.dmg = rf('dmg')
        item.delay = rf('delay')
        item.dps = rf('dps')
        item.skill = rf('skill')

    icon_size = struct.unpack_from('<I', rec_en, ICON_OFFSET)[0]
    if icon_size > 0 and ICON_DATA + icon_size <= len(rec_en):
        item.icon_size = icon_size
        item.icon_data = rec_en[ICON_DATA:ICON_DATA + icon_size]
    return item


def _patch_record(rec: bytearray, entry: dict, item_type: int, fmt: Optional[str] = None) -> None:
    if fmt is None:
        fmt = format_for_stride(len(rec))
    layout = layout_for_type(item_type)

    if 'jobs_list' in entry and 'jobs' not in entry:
        entry = {**entry, 'jobs': encode_jobs(entry['jobs_list'])}
    if 'flags_decoded' in entry and 'flags' not in entry:
        entry = {**entry, 'flags': encode_flags(entry['flags_decoded'])}

    def _set(key, name=None):
        if key in entry and entry[key] is not None:
            write_field(rec, layout, fmt, name or key, int(entry[key]))

    _set('flags')
    _set('stack')
    _set('resource_id')
    _set('targets')
    if item_type in (3, 4):
        _set('level')
        _set('slots')
        _set('races')
        _set('jobs')
        _set('superior_level')
    if item_type == 4:
        _set('kind', 'type')
        _set('dmg')
        _set('delay')
        _set('dps')
        _set('skill')

    # Require at least one of the *display* text fields explicitly -- 'name' alone is ambiguous
    # (callers sometimes pass it as a stand-in for a server-only internal/sort name that isn't
    # real display text) and would otherwise default singular/plural from it and blank the
    # description. A real display-text edit should always know singular/plural/description too.
    text_keys = {'singular', 'plural', 'description'}
    if text_keys & entry.keys():
        text_off = text_offset_for(item_type, fmt)
        strings = [
            entry.get('name', ''),
            int(entry.get('article', 0) or 0),
            entry.get('singular', entry.get('name', '')),
            entry.get('plural', entry.get('name', '') + 's'),
            entry.get('description', ''),
        ]
        _write_strings(strings, text_off, rec)


def build_record(entry: dict, item_type: int, fmt: str = FORMAT_LEGACY) -> bytes:
    stride = STRIDE_BY_FORMAT[fmt]
    rec = bytearray(stride)
    struct.pack_into('<H', rec, 0x00, item_type)
    rec[stride - 1] = TERMINATOR
    _patch_record(rec, entry, item_type, fmt)
    return bytes(rec)


def parse_dat(cat_name: str, base_id: int, item_type: int, en_rom: str, jp_rom: str):
    """Generator: yields ItemRecord for every real item in one DAT category."""
    en_path = dat_path(en_rom)
    jp_path = dat_path(jp_rom)
    if not en_path.exists():
        return
    en = ItemDat.load(en_path)
    jp = ItemDat.load(jp_path) if jp_path.exists() and jp_path != en_path else None
    for idx in range(en.count):
        item_id = base_id + idx
        rec_en = en.record(idx)
        rec_jp = jp.record(idx) if jp is not None and idx < jp.count else None
        item = _parse_record(item_id, rec_en, rec_jp, item_type, str(en_path),
                              dat_ui=en_rom, fmt=en.format, record_index=idx, category=cat_name)
        if item is not None:
            yield item


# ── mission_toolkit-specific glue ────────────────────────────────────────────

def category_for_item(item_id: int):
    """Which ITEM_DATS row actually holds this id -- resolves by trying every
    range that contains it (several 'general' ranges are non-contiguous) and
    picking the first whose real record count on disk covers the offset."""
    candidates = [row for row in ITEM_DATS if row[1] <= item_id]
    candidates.sort(key=lambda r: -r[1])
    for cat_name, base_id, item_type, en_rom, jp_rom in candidates:
        p = dat_path(en_rom)
        if not p.exists():
            continue
        idx = item_id - base_id
        if idx < 0:
            continue
        try:
            if idx < record_count(p):
                return cat_name, base_id, item_type, en_rom, jp_rom
        except ValueError:
            continue
    return None


def read_client_item(item_id: int) -> Optional[ItemRecord]:
    """Read one item's real client-DAT record, or None if no DAT covers it /
    FFXI isn't configured / the slot is empty."""
    try:
        found = category_for_item(item_id)
    except ValueError:
        return None
    if found is None:
        return None
    cat_name, base_id, item_type, en_rom, jp_rom = found
    en_path = dat_path(en_rom)
    jp_path = dat_path(jp_rom)
    idx = item_id - base_id
    en = ItemDat.load(en_path)
    if idx >= en.count:
        return None
    jp = ItemDat.load(jp_path) if jp_path.exists() and jp_path != en_path else None
    rec_en = en.record(idx)
    rec_jp = jp.record(idx) if jp is not None and idx < jp.count else None
    return _parse_record(item_id, rec_en, rec_jp, item_type, str(en_path),
                          dat_ui=en_rom, fmt=en.format, record_index=idx, category=cat_name)


def _dat_backup_root() -> Path:
    return Path(__file__).parent / 'data' / 'item_dat_backups'


def _dat_backup_key(rom_path: str) -> str:
    return rom_path.replace('/', '_').replace('\\', '_')


def backup_dat_snapshot(path: Path, rom_path: str) -> Optional[Path]:
    """Snapshot a DAT before EVERY edit, not just its first -- a single one-time backup taken
    on the first-ever edit is worthless if that first edit is itself the corrupting one (real
    incident: item 10478 / Euxine Coat +3, 2026-09-24 -- the "pristine" backup already contained
    the corruption, so the restore button just wrote corruption back over corruption).

    Two tiers, both keyed by the ROM-relative path (several item categories share numeric DAT
    filenames under different ROM/x/ folders, so the bare filename alone would collide):
      - `<key>.orig` -- the true first-ever-seen state, written once and never overwritten or
        pruned. Permanent floor to restore to no matter how much later history is lost/pruned.
      - `<key>/<timestamp>.dat` -- one rolling snapshot per edit, so a restore can reach back to
        right before whichever specific edit broke something, not just all the way to pristine.
        Pruned to `backup_retention_count` (same user setting/pattern as build_database.py's
        backup_database_file(), read fresh here so a Settings change applies to the very next
        edit) -- unbounded growth would otherwise fill the disk with whole-DAT copies."""
    if not path.exists():
        return None
    backup_root = _dat_backup_root()
    backup_root.mkdir(parents=True, exist_ok=True)
    key = _dat_backup_key(rom_path)

    pristine = backup_root / (key + '.orig')
    if not pristine.exists():
        pristine.write_bytes(path.read_bytes())

    import shutil
    from datetime import datetime
    snap_dir = backup_root / key
    snap_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    dest = snap_dir / f"{stamp}.dat"
    shutil.copy2(path, dest)

    try:
        con = sqlite3.connect(str(settings_mod.DB_PATH))
        try:
            retention = int(settings_mod.get(con, "backup_retention_count")
                             or settings_mod.DEFAULTS["backup_retention_count"])
        finally:
            con.close()
    except (ValueError, TypeError, sqlite3.Error):
        retention = int(settings_mod.DEFAULTS["backup_retention_count"])
    snapshots = sorted(snap_dir.glob("*.dat"))
    for old in (snapshots[:-retention] if retention > 0 else snapshots):
        old.unlink()

    return dest


def backup_dat_once(path: Path, rom_path: str) -> Optional[Path]:
    """Deprecated alias -- kept only so any stray external caller doesn't hard-fail. New code
    should call backup_dat_snapshot(), which supersedes this (see its docstring for why a
    one-time-only backup is unsafe)."""
    return backup_dat_snapshot(path, rom_path)


def patch_client_item(item_id: int, fields: dict) -> dict:
    """Patch an existing item's client-DAT record in place. `fields` uses the
    same key names as ItemRecord (level, jobs (or jobs_list), races, slots,
    superior_level, dmg, delay, dps, skill, flags (or flags_decoded), stack,
    resource_id, targets, name/singular/plural/description). Returns a small
    report dict; raises if the item/DAT can't be found."""
    found = category_for_item(item_id)
    if found is None:
        raise ValueError(f'no client DAT covers item id {item_id}')
    cat_name, base_id, item_type, en_rom, jp_rom = found
    target = dat_target()
    src_path = dat_write_source(en_rom)
    dest_path = dat_write_dest(en_rom)
    idx = item_id - base_id
    dat = ItemDat.load(src_path)
    if idx >= dat.count:
        raise ValueError(f'item id {item_id} has no record in {cat_name} ({src_path})')
    backup_dat_snapshot(dest_path, en_rom)
    rec = bytearray(dat.record(idx))
    _patch_record(rec, fields, item_type, dat.format)
    dat.set_record(idx, bytes(rec))
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(dat.encrypted())
    return {'ok': True, 'category': cat_name, 'dat': str(dest_path), 'dat_ui': en_rom,
            'record_index': idx, 'format': dat.format, 'fields': list(fields.keys()),
            'target': target}


def free_slots(cat_name: str, count: int) -> list:
    """First `count` empty (placeholder-name) record indices in a DAT category."""
    row = next((r for r in ITEM_DATS if r[0] == cat_name), None)
    if row is None:
        raise ValueError(f'unknown item DAT category {cat_name!r}')
    _, base_id, item_type, en_rom, _ = row
    en_path = dat_write_source(en_rom)
    if not en_path.exists():
        raise ValueError(f'DAT not found for category {cat_name!r}: {en_path}')
    dat = ItemDat.load(en_path)
    out = []
    for idx in range(dat.count):
        rec = dat.record(idx)
        text_off = _resolve_text_offset(rec, item_type, dat.format)
        strings = _read_strings(rec, text_off) if text_off is not None else []
        if not strings or not strings[0] or strings[0] == '.':
            out.append(idx)
        if len(out) >= count:
            break
    return out


def list_dat_backups() -> list:
    """Every DAT backup on disk, newest first: each `.orig` pristine (id 'orig', never pruned)
    plus every per-edit rolling snapshot under its key's subfolder (id = its timestamp), so the
    UI can restore to any specific point, not just all the way back to pristine."""
    backup_dir = _dat_backup_root()
    if not backup_dir.exists():
        return []
    out = []
    for p in backup_dir.glob('*.orig'):
        key = p.stem[:-len('.orig')] if p.stem.endswith('.orig') else p.stem
        out.append({'key': key, 'id': 'orig', 'kind': 'pristine',
                    'file': p.name, 'size': p.stat().st_size, 'mtime': p.stat().st_mtime})
    for snap_dir in backup_dir.iterdir():
        if not snap_dir.is_dir():
            continue
        key = snap_dir.name
        for p in snap_dir.glob('*.dat'):
            out.append({'key': key, 'id': p.stem, 'kind': 'snapshot',
                        'file': p.name, 'size': p.stat().st_size, 'mtime': p.stat().st_mtime})
    out.sort(key=lambda r: r['mtime'], reverse=True)
    return out


def pivot_manifest() -> dict:
    """Every DAT currently sitting in the Xi-Pivot overlay folder, for the export/preview UI."""
    root = pivot_root()
    if not root.exists():
        return {"root": str(root), "files": []}
    files = [{"rom_path": str(p.relative_to(root)).replace('\\', '/'), "size": p.stat().st_size}
             for p in root.rglob('*') if p.is_file()]
    return {"root": str(root), "files": files}


def restore_dat_backup(rom_path: str, backup_id: Optional[str] = None) -> dict:
    """Restore a DAT backup back over the LIVE install copy, regardless of the current
    item_dat_target mode -- the live install is what real gameplay reads, so that is what
    "revert my mistake" should always mean here. Xi-Pivot copies are meant to be disposable
    (regenerate by re-running the edit), so they are not covered by this restore path.

    `backup_id` picks which snapshot: 'orig' for the permanent pristine, a specific rolling
    snapshot's timestamp id, or omitted/None for the newest rolling snapshot (falling back to
    pristine if no rolling snapshots exist yet -- e.g. a DAT edited only once so far)."""
    backup_dir = _dat_backup_root()
    key = _dat_backup_key(rom_path)
    pristine = backup_dir / (key + '.orig')
    snap_dir = backup_dir / key

    if backup_id == 'orig':
        src = pristine
    elif backup_id:
        src = snap_dir / f'{backup_id}.dat'
    else:
        snapshots = sorted(snap_dir.glob('*.dat')) if snap_dir.exists() else []
        src = snapshots[-1] if snapshots else pristine

    if not src.exists():
        raise ValueError(f'no backup found for {rom_path} (id={backup_id!r})')
    dest = dat_path(rom_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())
    return {'ok': True, 'dat_ui': rom_path, 'restored_to': str(dest),
            'restored_from': src.name, 'backup_id': backup_id or ('latest' if src != pristine else 'orig')}


def inject_client_item(cat_name: str, entry: dict) -> dict:
    """Write a brand-new item into the first free slot of `cat_name`'s DAT.
    Returns {'ok', 'item_id', 'category', ...}. Caller is responsible for then
    inserting the matching item_basic/item_equipment/... row at the same id
    (item_edit.create_item does both together)."""
    row = next((r for r in ITEM_DATS if r[0] == cat_name), None)
    if row is None:
        raise ValueError(f'unknown item DAT category {cat_name!r}')
    _, base_id, item_type, en_rom, _ = row
    target = dat_target()
    src_path = dat_write_source(en_rom)
    dest_path = dat_write_dest(en_rom)
    slots = free_slots(cat_name, 1)
    if not slots:
        raise ValueError(f'no free slots left in {cat_name} ({src_path})')
    idx = slots[0]
    backup_dat_snapshot(dest_path, en_rom)
    dat = ItemDat.load(src_path)
    new_rec = build_record(entry, item_type, dat.format)
    dat.set_record(idx, new_rec)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(dat.encrypted())
    item_id = base_id + idx
    return {'ok': True, 'item_id': item_id, 'category': cat_name, 'record_index': idx,
            'dat': str(dest_path), 'dat_ui': en_rom, 'format': dat.format, 'target': target}


def item_to_dict(item: ItemRecord) -> dict:
    d = asdict(item)
    d.pop('icon_data', None)
    d.pop('dat', None)
    d['flags_decoded'] = decode_flags(d['flags'])
    if d.get('jobs'):
        d['jobs_list'] = decode_jobs(d['jobs'])
    return d

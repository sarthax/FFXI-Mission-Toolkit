"""Operator-verified (mob, anim, skill) triples used to sanity-check the bridge after client/addon changes.

Only entries confirmed visually in the live Valhalla client belong here.
"""
from __future__ import annotations

import time

VERIFIED = (
    # Haraal Ja NM rows 3900-3904 (anims 1320-1324): confirmed to look correct for the NM, 2026-10-02.
    ("Stealthlord Haraal Ja", 1320, 3900),
    ("Stealthlord Haraal Ja", 1321, 3901),
    ("Stealthlord Haraal Ja", 1322, 3902),
    ("Stealthlord Haraal Ja", 1323, 3903),
    ("Stealthlord Haraal Ja", 1324, 3904),
    # Mumor: 2036/2037 played in-game; the capture says 2037=Samba, 2038=Waltz, so the exact
    # name mapping is UNRESOLVED (possible one-off shift). Listed as "plays", not as named.
    ("Mumor", 2036, 2899),
    ("Mumor", 2037, 2899),
)


def run_all(bridge, gap: float = 8.0):
    """Queue every verified triple through the bridge for a quick eyeball pass (find first)."""
    last = None
    for mob, anim, skill in VERIFIED:
        if mob != last:
            bridge.find(mob)
            last = mob
        bridge.play(anim, skill)
        time.sleep(gap)

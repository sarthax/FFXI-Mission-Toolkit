#!/usr/bin/env python3
import json
from pathlib import Path
P=Path(__file__).resolve().parent/"fixtures"/"absolute_virtue_behavior_probe.json"
def main():
    p=json.loads(P.read_text(encoding="utf-8"))
    kinds={d["kind"] for d in p["dependencies"]}
    assert {"spawn_from_death","inherit_runtime_target","cross_entity_state","hp_threshold","timed_random_action","player_action_response","magic_response","spell_override","cleanup","loot_override"} <= kinds
    required=set(p["generic_map_required"])
    assert {"probability_guard","delayed_effect","runtime_state_transfer","mutable_ability_set","combat_modifier"} <= required
    assert len(p["hooks"])>=9
    print("Absolute Virtue scripted-NM behavior probe: PASS")
    print("hooks",len(p["hooks"]),"dependencies",len(p["dependencies"]),"map_classes",len(required))
    return 0
if __name__=="__main__": raise SystemExit(main())

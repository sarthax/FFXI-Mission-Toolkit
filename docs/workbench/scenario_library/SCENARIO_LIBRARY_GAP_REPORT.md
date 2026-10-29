# Scenario Library Gap Report (DRAFT)

- **G-01** No item or key-item expectation/oracle in `ScenarioExpectationSchema`; readback exists only as MCP tools (inventory, container_items, key_items).
- **G-02** No quest/mission state readback tool found; quest scenarios can only assert that an event opened.
- **G-03** Client-vs-server ID offset: npc_list ids and csids come from server source; every quest candidate needs dat-extractor verification before execution.
- **G-04** Prerequisites (levels, rank, prior quests, imprimatur) are not characterized for any quest or Assault scenario.
- **G-05** Toolkit execution_preflight supports only MOG-09; no publish path or categories (see the #1348 proposal).
- **G-06** Domains not researched: missions, status effects, doors/switches, captures, Feature Trace, Behavior Inspector.
- **G-07** No recorded results for the Argus, Leujaoam, sweep and patrol scenario files; they are source-supported only.
- **G-08** Duplicate NPC names across zones (e.g. Brygid, Babenn, Kopuro-Popuro) need a zone-qualified npc_list query; the extract used the first row whose id resolves to the script zone.
- **G-09** Combat and status-effect entries are design-only (no recorded runs).

Historical failures are not treated as expected failures.

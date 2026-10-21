# Salvage R5 — source-backed gameplay draft

Issue [#1254](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1254), parent #1197. DSP [`main@86d4467d446569c741d76d296e640c3b844ad844`](https://github.com/sarthax/darkstar-to-valhalla/tree/86d4467d446569c741d76d296e640c3b844ad844); **live deployed revision and configuration UNKNOWN**. Design-only; no execution or merges.

## Scenario and oracle matrix

| Case | Scenario | Lane | Source-based expectation (runtime UNKNOWN) |
|---|---|---|---|
| SAL-01 | Read-only Pathos/status baseline | `needs-readback` | Source describes 5 Pathos on entry; actual pre-existing effect masks/stage must be read, not fabricated |
| SAL-02 | Arrapago entry applies timed Pathos | `needs-mutation` | Five effects added with duration 6000 seconds and stage 1/progress 0 in Lua; client effect timing and persistence require verification |
| SAL-03 | Cell use outside Remnants is rejected | `needs-mutation` | onCellItemCheck returns 55 outside zones 73–76; client refusal and unchanged item/status need readback |
| SAL-04 | Cell removes only its debuff mask bits | `needs-mutation` | newpower = bit.band(oldpower,bit.bnot(value)); instance cellsUsed increments; pet mirroring only for 3 defined effects |
| SAL-05 | Sealed Bhaflau door rejects progression | `needs-mutation` | onDoorOpen returns false unless animation is closed and unSealed==1; actual per-door trigger must be bound first |
| SAL-06 | Bhaflau fixed crate temporary-item selection | `needs-mutation` | tempBoxPickCellItems initializes randomized but source-bounded item IDs; tempBoxFinish decrements when addTempItem accepted and player lacks the temp item |
| SAL-07 | Instance time-expiry/failure and Pathos teardown | `needs-mutation` | onInstanceFailure sends client event, normal exit strips five effects; expiry callback, event completion and proper cleanup need independent observation |

## Key source findings

- [`salvage.lua:43–101`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/globals/salvage.lua#L43-L101): cell validation is zone-specific; Pathos `power` updates are bitmask operations, pet clearing limited to specific effects; `cellsUsed` is an **instance localvar**, not `char_vars`.
- [`arrapago_remnants.lua:7–36`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Arrapago_Remnants/instances/arrapago_remnants.lua#L7-L36): stage/progress initialization and five time-bounded Pathos; no entry-permit assertion from an admin warp.
- [`door_util.lua:25–56`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bhaflau_Remnants/door_util.lua#L25-L56): a sealed door does not advance absent `unSealed=1`; this says nothing about the unbound NPC/event dialogue.
- [`Armoury_Crate.lua:17–29`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bhaflau_Remnants/npcs/Armoury_Crate.lua#L17-L29) and [`salvage.lua:285–363`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/globals/salvage.lua#L285-L363): fixed crate uses temporary-item selection; random cell pool must be read after initialization, not guessed.
- [`arrapago_remnants.lua:39–64`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Arrapago_Remnants/instances/arrapago_remnants.lua#L39-L64) and [`bhaflau_remnants.lua:143–180`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bhaflau_Remnants/instances/bhaflau_remnants.lua#L143-L180): timer/failure events and exit cleanup are distinct; failures are not success evidence.

## Ranked observe-now

**None confirmed.** Current bounded supervisor endpoints cannot provide active status-effect power, instance stage/progress, door localvars or temporary-items. SAL-01 is read-only in intent but **needs-readback**, not observe-now.

## Integration gates and UNKNOWNs

- Source code on main is not evidence that deployed server runs it. Instances may vary by Remnants zone; do not project Arrapago behavior onto incomplete branches.
- Need bounded instance `stage,progress,cellsUsed,timeLimit`, door `unSealed`, character Pathos mask/duration and `LOC_TEMPITEMS` queries; no generic SQL/GM access proposed.
- Correct NPC, client event option, and cell item/value require independent source bindings. No guessed IDs, fixed random rewards, or completion outcomes.
- Mutation tests must be explicitly approved using isolated characters, teardown and quarantine. No direct runner/supervisor edit.
- `data/testing/domain_drafts/salvage.json` is staging, not canonical. Contract owner #1259 must review optional fields before import.

## Full case definitions

See staged JSON for stable IDs, BDD, 4 ordered steps per case, assertion IDs, source paths and line range, readback, cleanup, and explicitly NOT_RUN status.

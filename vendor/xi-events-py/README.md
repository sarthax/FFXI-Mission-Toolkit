# xi-events

Decompiles FFXI event-script bytecode to readable Lua.

Input data (`events.ndjson.gz`, `events_actors.ndjson.gz`, `strings.ndjson.gz`,
`entities.ndjson.gz`, optional `items.ndjson.gz`) ships as release assets on
[sruon/FFXI-Resources](https://github.com/sruon/FFXI-Resources/releases) —
download the latest release, extract somewhere, and point
`Dataset.from_dist(...)` at the directory containing the `.ndjson.gz` files.

```python
from xi_events import Dataset, decompile

ds = Dataset.from_dist("path/to/FFXI-Resources/dist")
print(decompile(ds.fixture(zone_id=235, actor_id=17739778, event_id=100)))
```

```lua
function event_100(npc, player, params)
    params[7] = 553
    npc:lookAtAndTalk(player)
    npc:say(7468)  -- I say, are you an adventurer? Looking for some work?
    player:waitForKeypress()
    result = npc:dialog(7469, 0, 0)  -- Are you looking for work? Yes. No.
    if result == 0 then
        npc:loadExtScheduler("tlk0", npc, 238)
        npc:say(7471)  -- Let me introduce myself...
        ...
        result2 = 0
    elseif result == 1 then
        npc:loadExtScheduler("har0", npc, 238)
        npc:say(7470)  -- Then I have no business with you. Out, I say! Out!
        result2 = 1073741824
    end
end
```

## Layout

```
disassemble  ->  CFG  ->  structural recovery  ->  Lua AST  ->  text
```

| Module              | Role                                                     |
|---------------------|----------------------------------------------------------|
| `dataset.py`        | Load the ndjson dataset, build indexes, return `Fixture` |
| `disasm.py`         | Recursive-descent disassembler                           |
| `cfg.py`            | Basic blocks + typed edges (fallthrough / branch / goto) |
| `structure.py`      | if/else recovery via immediate post-dominators           |
| `emit.py`           | Structured tree -> luaparser AST -> Lua text             |
| `work_area.py`      | Decode FFXI 16-bit work-area addresses                   |
| `registry.py`       | `OpDef` + `@op` decorator                                |
| `opcodes.py`        | Hand-refined emit functions (~50 ops)                    |
| `opcodes_auto.py`   | Auto-generated stubs for all 218 ops                     |
| `custom_parsers.py` | Variable-length opcode parsers                           |

## Adding or refining an opcode

Edit `opcodes.py`. One `@op(...)` block per opcode; the decorator overwrites
whatever `opcodes_auto` registered for that code.

```python
@op(0x1D, "PRINT_EVENT_MESSAGE", operands=[("message", "u16")])
def print_event_message(ctx, a):
    return ctx.invoke("npc", "say", [ctx.value(a.message)])
```

Operand types: `u8` `u16` `s16` `u32` (little-endian). Emit returns a
luaparser AST node, a list, or `None`. For variable-length opcodes, write a
`_parse_xxx(data, pos) -> (size, dict)` and pass via `custom_parse=`.

## Regenerating `opcodes_auto.py`

`xi_events/opcodes_meta.json` is the catalog source of truth. To add a new
opcode, edit the JSON directly, then:

```bash
python scripts/generate_opcodes.py
```

## Dev scripts

|                         |                                          |
|-------------------------|------------------------------------------|
| `batch_test_dataset.py` | Decompile every event; report pass/fail  |
| `generate_opcodes.py`   | Regenerate `opcodes_auto.py` from JSON   |

`XI_DIST` env var points at the dist directory; otherwise `./dist`.

## Dependencies

```bash
pip install luaparser
```

## Tests

```bash
PYTHONPATH=. python tests/test_horatius.py
```

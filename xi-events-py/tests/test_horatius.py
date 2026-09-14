"""Smoke test: decompile Horatius event 100."""

from luaparser import ast as lua_ast

from xi_events import Fixture, decompile

# Bastok Markets / Horatius (zone 235, actor 17739778) event 100 — v2 schema:
# event-self-contained bytecode, entrypoint 0.
_BYTECODE_HEX = (
    "03091000801EF0FFFF7F1D01802324028003800380250200100380006D005B0480"
    "F8FFFF7FF8FFFF7F746C6B301D0580235E69646C301D0680235B0480F8FFFF7FF8"
    "FFFF7F74686B311D0780231D0880235B0480F8FFFF7FF8FFFF7F74686B321D0980"
    "2303011003800190000200100A800090005B0480F8FFFF7FF8FFFF7F686172301D"
    "0B80230301100C800190002100"
)
_IMED = [
    553,
    7468,
    7469,
    0,
    238,
    7471,
    7472,
    7473,
    7474,
    7475,
    1,
    7470,
    1073741824,
    7476,
    7477,
    201,
    7489,
    9208,
    30,
    9209,
    9210,
]
_STRINGS = {
    7468: "I say, are you an adventurer? Looking for some work?",
    7469: "Are you looking for work? Yes. No.",
    7470: "Then I have no business with you. Out, I say! Out!",
    7471: "Let me introduce myself. I am Horatius, the foremost gem collector in all of Bastok.",
    7472: "I've collected every single kind of precious gem, but now I want to get my hands on a rare stone of a different kind.",
    7473: "I'd like to get my hands on something called %.",
    7474: "As you can guess from the name, the Dangruf Wadi is where you'd want to look. What's more, legend says that it can only be found on bright, sunny days.",
    7475: "If you manage to get your hands on %, bring it to me. You will be greatly rewarded.",
}


def _fixture() -> Fixture:
    return Fixture(
        zone_id=235,
        actor_id=17739778,
        block=0,
        idx=1,
        event_id=100,
        bytecode=bytes.fromhex(_BYTECODE_HEX),
        entrypoint=1,
        imed_data=_IMED,
        strings=_STRINGS,
        entities={},
    )


def test_decompiles_to_valid_lua():
    src = decompile(_fixture(), comments=False)
    fn = lua_ast.parse(src).body.body[0]
    assert type(fn).__name__ == "Function"
    assert fn.name.id == "event_100"


def test_bare_mode_drops_comments():
    src = decompile(_fixture(), comments=False)
    assert "--" not in src
    assert "I say, are you" not in src
    assert "-- imed:" not in src


def test_contains_expected_messages():
    src = decompile(_fixture())
    assert "I say, are you an adventurer" in src
    assert "Then I have no business with you" in src
    assert "elseif result == 1 then" in src


def test_summary_header():
    src = decompile(_fixture())
    assert "-- params: 7" in src
    assert "-- writes:  result, result2" in src
    assert "-- imed:" in src


if __name__ == "__main__":
    test_decompiles_to_valid_lua()
    test_bare_mode_drops_comments()
    test_contains_expected_messages()
    test_summary_header()
    print("OK")

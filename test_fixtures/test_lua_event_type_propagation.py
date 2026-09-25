#!/usr/bin/env python3
"""Regression checks for conservative Lua event local type propagation."""
from workbench.analyzers.server.lua_events import FUNC_RE, typed_calls


def main():
    text="""
function onEventFinish(player, csid, option)
    local p = player
    local battlefield = player:getBattlefield()
    p:getID()
    battlefield:getArea()
end
"""
    fn=next(FUNC_RE.finditer(text))
    calls=typed_calls(
        text,
        fn.start(),
        len(text),
        fn,
        {("CLuaBaseEntity","getBattlefield"):"CLuaBattlefield"},
    )
    by_method={call["method"]:call for call in calls}
    assert by_method["getID"]["class_hint"]=="CLuaBaseEntity",calls
    assert by_method["getID"]["class_hint_source"]=="LOCAL_ALIAS",calls
    assert by_method["getArea"]["class_hint"]=="CLuaBattlefield",calls
    assert by_method["getArea"]["class_hint_source"]=="CONFIGURED_RETURN_TYPE",calls

    no_hint=typed_calls(text,fn.start(),len(text),fn,{})
    no_hint_by_method={call["method"]:call for call in no_hint}
    assert no_hint_by_method["getArea"]["class_hint"] is None,no_hint
    print("Lua event type propagation self-test: PASS")


if __name__=="__main__":
    main()

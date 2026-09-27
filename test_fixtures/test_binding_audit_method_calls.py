#!/usr/bin/env python3
"""Binding audit must distinguish Lua method definitions from method calls."""
from pathlib import Path
import tempfile

import backport_binding_audit as bba


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        f=root/"test.lua"
        f.write_text(
            "function content:entryRequirement(player) return true end\n"
            "local x = player:getLocalVar('x')\n",
            encoding="utf-8",
        )
        calls=bba.collect_method_calls(root)
        assert "entryRequirement" not in calls,calls
        assert "getLocalVar" in calls,calls

    print("binding audit method-call self-test: PASS")


if __name__=="__main__":
    main()

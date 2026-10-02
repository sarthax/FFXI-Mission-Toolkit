#!/usr/bin/env python3
"""Validate provenance discipline in the DSP namespace conversion map."""
from __future__ import annotations

import re
import sys

from workbench.packages.migration import lua_convert as blc

DATED_SECTION_RE = re.compile(r"_\d{4}-\d{2}-\d{2}$")
LSB_FILE_MARKER = "lua_base_entity.cpp"
LEGACY_SECTIONS = ("method_renames", "simple_families", "reshaped_families")


def lint() -> int:
    m = blc.load_map()
    errors: list[str] = []
    warnings: list[str] = []

    for key, value in m.items():
        if key.startswith("_") or not isinstance(value, dict):
            continue
        if DATED_SECTION_RE.search(key) and "_readme" not in value:
            errors.append(
                f"section '{key}' has a dated name but no '_readme' explaining "
                f"what it covers / what it was checked against"
            )

    verified_old_dsp = set(m.get("old_dsp_reference_verified_2026-09-13", {}).keys()) - {"_readme"}

    for section in LEGACY_SECTIONS:
        entries = m.get(section, {})
        for name, spec in entries.items():
            if name.startswith("_") or not isinstance(spec, dict):
                continue
            if not spec.get("source") and not spec.get("evidence") and not spec.get("note"):
                errors.append(
                    f"{section}.{name} has no 'source'/'evidence'/'note' field -- every "
                    f"entry must cite real DSP source (or explain why it doesn't need "
                    f"its own), per this map's own long-standing rule"
                )
                continue
            source_text = str(spec.get("source", "")) + str(spec.get("evidence", ""))
            if LSB_FILE_MARKER in source_text and name not in verified_old_dsp:
                warnings.append(
                    f"{section}.{name} was checked against a LandSandBoat-shaped path "
                    f"({LSB_FILE_MARKER}) and has no override in "
                    f"old_dsp_reference_verified_2026-09-13 -- not yet confirmed for "
                    f"the real production target, use with caution"
                )

    for warning in warnings:
        print(f"WARN   {warning}")
    for error in errors:
        print(f"ERROR  {error}")

    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(lint())

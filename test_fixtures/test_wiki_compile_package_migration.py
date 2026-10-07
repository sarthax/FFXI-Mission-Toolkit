from __future__ import annotations

import sys
from pathlib import Path

from workbench.devtools.reference import wiki_compile as canonical
from workbench.runtime.paths import DATABASE_PATH, VENDOR_ROOT


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "wiki_compile.py").exists()

    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.DUMP_PATH == VENDOR_ROOT / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"

    assert canonical.title_from_query("https://www.bg-wiki.com/ffxi/The_Siren%27s_Tear") == "The Siren's Tear"
    assert canonical.normalize("Archer's Ring") == "archersring"

    links = canonical.extract_entity_links(
        "[[Leujaoam Sanctum]] [[Earth Crystal|crystal]] [[Category:Assault]] "
        "{{Item Tooltip|Siren's Tear}} [[Leujaoam Sanctum#Map]]"
    )
    assert links == ["Leujaoam Sanctum", "Earth Crystal", "Siren's Tear"]

    sections = canonical.extract_wiki_sections(
        "Intro text\n== Walkthrough ==\nDo the [[Thing]].\n== Rewards ==\nIgnored.\n"
    )
    assert "Walkthrough" in sections
    assert "Rewards" not in sections

    print("Wiki compiler package migration: PASS")


if __name__ == "__main__":
    main()

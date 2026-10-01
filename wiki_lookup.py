#!/usr/bin/env python3
"""Compatibility CLI/import wrapper for Development wiki lookup tooling."""
from workbench.devtools.reference.wiki_lookup import *  # noqa: F401,F403
from workbench.devtools.reference.wiki_lookup import main


if __name__ == "__main__":
    main()

"""Compatibility alias: the Item DAT reader/writer is Client-owned (``workbench.client.dat.item_dat_tools``)."""
import sys

from workbench.client.dat import item_dat_tools as _item_dat_tools

sys.modules[__name__] = _item_dat_tools

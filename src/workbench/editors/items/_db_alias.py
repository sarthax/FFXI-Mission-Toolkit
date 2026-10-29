"""Compatibility alias: the item-table alias connection is Core (``workbench.runtime.item_db_alias``)."""
import sys

from workbench.runtime import item_db_alias as _item_db_alias

sys.modules[__name__] = _item_db_alias

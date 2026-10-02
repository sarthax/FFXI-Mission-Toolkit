"""Checkout-local Campaign name catalog for Character Editor."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .progression_catalog import mission_catalog

CAMPAIGN_LOG_ID = 8


def campaign_catalog(server_root: Path | str | None) -> dict[str, Any]:
    catalog = mission_catalog(server_root)
    source = dict(catalog.get("source") or {})
    area = (catalog.get("areas") or {}).get(str(CAMPAIGN_LOG_ID), {})
    items = {
        str(item_id): row
        for item_id, row in sorted(
            ((int(raw_id), dict(row)) for raw_id, row in area.items()),
            key=lambda item: item[0],
        )
        if 0 <= item_id < 512
    }
    return {
        "source": source,
        "log_id": CAMPAIGN_LOG_ID,
        "items": items,
    }

"""Audited profile for LSB Curio Vendor Moogle stock.

Curio stock is not an ordinary static shop. Each explicit item row is gated by a
required key-item literal and may also be restricted to one zone. The parser
preserves those conditions instead of flattening Curio into generic SOLD_BY stock.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Any


_ITEM_EXPR = r"(?:xi\.item\.[A-Z0-9_]+|\d+)"
_KEY_ITEM_EXPR = r"(?:xi\.keyItem\.[A-Z0-9_]+|\d+)"
_ZONE_EXPR = r"(?:xi\.zone\.[A-Z0-9_]+|\d+)"
_CATEGORY_EXPR = r"xi\.shop\.curio\.([A-Za-z0-9_]+)"


@dataclass(frozen=True)
class CurioItem:
    item_literal: str
    price: int
    required_key_item_literal: str
    zone_literal: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CurioCategory:
    category: str
    source_path: str
    items: tuple[CurioItem, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "source_path": self.source_path,
            "items": [item.as_dict() for item in self.items],
        }


def _balanced_brace_block(text: str, start: int) -> str | None:
    depth = 0
    in_string: str | None = None
    escaped = False
    for index in range(start, len(text)):
        ch = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            continue
        if ch in {"'", '"'}:
            in_string = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def parse_curio_vendor_stock(
    text: str, *, source_path: str = "scripts/globals/shop.lua"
) -> dict[str, Any]:
    """Parse the explicit LSB ``xi.shop.curioVendorMoogleStock`` table.

    Only literal item/price/key-item/optional-zone rows are accepted. Dynamic
    expressions are reported as warnings rather than interpreted.
    """
    marker = re.search(r"\bxi\.shop\.curioVendorMoogleStock\s*=\s*\{", text)
    result = {
        "status": "UNSUPPORTED",
        "source_path": source_path,
        "profile": "CURIO_VENDOR_MOOGLE",
        "categories": (),
        "warnings": [],
    }
    if not marker:
        result["warnings"].append("Curio Vendor Moogle stock table was not found.")
        return result

    start = text.find("{", marker.start())
    table = _balanced_brace_block(text, start)
    if not table:
        result["warnings"].append("Curio Vendor Moogle stock table is malformed.")
        return result

    categories: list[CurioCategory] = []
    category_re = re.compile(r"\[\s*" + _CATEGORY_EXPR + r"\s*\]\s*=\s*\{")
    for match in category_re.finditer(table):
        brace = table.find("{", match.start())
        block = _balanced_brace_block(table, brace)
        if not block:
            result["warnings"].append(f"{match.group(1)}: malformed category table")
            continue

        items: list[CurioItem] = []
        row_re = re.compile(
            r"\{\s*(" + _ITEM_EXPR + r")\s*,\s*(\d+)\s*,\s*(" +
            _KEY_ITEM_EXPR + r")(?:\s*,\s*(" + _ZONE_EXPR + r"))?\s*\}"
        )
        for row in row_re.finditer(block):
            items.append(CurioItem(
                item_literal=row.group(1),
                price=int(row.group(2)),
                required_key_item_literal=row.group(3),
                zone_literal=row.group(4),
            ))

        # Count row-shaped braces so unsupported expressions remain visible.
        candidate_rows = len(re.findall(r"\{[^{}]+\}", block))
        if candidate_rows != len(items):
            result["warnings"].append(
                f"{match.group(1)}: decoded {len(items)} of {candidate_rows} stock rows"
            )
        categories.append(CurioCategory(match.group(1), source_path, tuple(items)))

    if not categories:
        result["warnings"].append("No supported Curio category blocks were decoded.")
        return result

    result["status"] = "OK"
    result["categories"] = tuple(categories)
    return result

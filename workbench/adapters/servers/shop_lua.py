"""Audited Lua shop-source adapters for acquisition evidence.

Supported patterns are intentionally narrow and source-shape driven:
- LSB-style pair-row stock tables passed to `xi.shop.general` / `xi.shop.nation`.
- Topaz-style flat alternating item/price arrays passed to `tpz.shop.general` / `tpz.shop.nation`.
- DSP-style flat alternating item/price arrays passed to `dsp.shop.general` / `dsp.shop.nation`.
- Modern LSB `scripts/data/guild_shops.lua` named shop blocks with structured stock rows.

File location is not part of detection: supported stock/call patterns may be extracted
from NPC, zone, instance, module, or other Lua files. The parser is evidence extraction,
not a Lua interpreter. Unsupported dynamic stock expressions are reported rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Any, Iterable


_ITEM_EXPR = r"(?:xi\.item\.[A-Z0-9_]+|\d+)"
_PRICE_EXPR = r"(?:\d+)"


@dataclass(frozen=True)
class ShopItem:
    item_literal: str
    price: int | None = None
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["metadata"] = dict(self.metadata or {})
        return row


@dataclass(frozen=True)
class ShopRecord:
    shop_id: str
    shop_kind: str
    vendor_name: str | None
    source_path: str
    source_family: str
    items: tuple[ShopItem, ...]
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "shop_id": self.shop_id,
            "shop_kind": self.shop_kind,
            "vendor_name": self.vendor_name,
            "source_path": self.source_path,
            "source_family": self.source_family,
            "items": [item.as_dict() for item in self.items],
            "metadata": dict(self.metadata or {}),
        }


def _vendor_from_path(source_path: str) -> str | None:
    name = source_path.replace("\\", "/").rsplit("/", 1)[-1]
    return name[:-4] if name.lower().endswith(".lua") else (name or None)


def _source_scope(source_path: str) -> str:
    path = source_path.replace("\\", "/").lower()
    if "/npcs/" in path:
        return "NPC"
    if "/instances/" in path or "/instance/" in path:
        return "INSTANCE"
    if path.endswith("/zone.lua") or "/zones/" in path:
        return "ZONE"
    return "OTHER"


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


def _local_stock_block(text: str) -> str | None:
    m = re.search(r"\blocal\s+stock\s*=\s*\{", text)
    if not m:
        m = re.search(r"\bstock\s*=\s*\{", text)
    if not m:
        return None
    brace = text.find("{", m.start())
    return _balanced_brace_block(text, brace)


def parse_npc_shop_script(text: str, *, source_path: str) -> dict[str, Any]:
    """Parse one regular/nation shop source conservatively, independent of file location."""
    calls = []
    for namespace, source_family in (("xi", "LSB"), ("tpz", "TOPAZ"), ("dsp", "DSP")):
        for kind in ("general", "nation"):
            pattern = rf"{namespace}\.shop\.{kind}\s*\(\s*player\s*,\s*stock\b"
            if re.search(pattern, text):
                calls.append((kind.upper(), namespace, source_family))

    result = {
        "status": "UNSUPPORTED",
        "source_path": source_path,
        "shop": None,
        "warnings": [],
    }
    if len(calls) != 1:
        result["warnings"].append(
            "Expected exactly one supported xi/tpz/dsp shop.general or shop.nation call using local stock."
        )
        return result

    block = _local_stock_block(text)
    if not block:
        result["warnings"].append("Supported shop call found but no local stock table was found.")
        return result

    items: list[ShopItem] = []
    inner = block[1:-1]
    # LSB pair-row stock has nested row braces. Do not apply this parser to
    # legacy DSP/Topaz flat alternating arrays, where the outer table is the
    # only brace pair.
    if "{" in inner:
        entry_re = re.compile(
            rf"\{{\s*({_ITEM_EXPR})\s*,\s*({_PRICE_EXPR})\s*(?:,\s*[^}}]+)?\}}"
        )
        for m in entry_re.finditer(inner):
            items.append(ShopItem(m.group(1), int(m.group(2)), {"stock_syntax": "PAIR_ROWS"}))

    # DSP/Topaz commonly use a flat alternating array:
    # { item_id, price, item_id, price, ... }.
    if not items:
        scrubbed = re.sub(r"--[^\n]*", "", block[1:-1])
        tokens = [token.strip() for token in scrubbed.split(",") if token.strip()]
        if tokens and len(tokens) % 2 == 0:
            flat_ok = True
            flat_items: list[ShopItem] = []
            for index in range(0, len(tokens), 2):
                item_token, price_token = tokens[index], tokens[index + 1]
                if not re.fullmatch(_ITEM_EXPR, item_token) or not re.fullmatch(_PRICE_EXPR, price_token):
                    flat_ok = False
                    break
                flat_items.append(ShopItem(item_token, int(price_token), {"stock_syntax": "FLAT_PAIRS"}))
            if flat_ok:
                items = flat_items

    if not items and block.strip() not in {"{}", "{\n}"}:
        result["warnings"].append(
            "Stock table exists but no supported static pair-row or flat item/price rows were decoded."
        )
        return result

    kind, namespace, source_family = calls[0]
    vendor = _vendor_from_path(source_path)
    shop = ShopRecord(
        shop_id=f"lua-shop:{source_path}",
        shop_kind=kind,
        vendor_name=vendor,
        source_path=source_path,
        source_family=source_family,
        items=tuple(items),
        metadata={
            "static_stock": True,
            "shop_namespace": namespace,
            "source_scope": _source_scope(source_path),
        },
    )
    result["status"] = "OK"
    result["shop"] = shop
    return result


def _named_table_block(text: str, name: str) -> str | None:
    pattern = re.compile(r"\[\s*['\"]" + re.escape(name) + r"['\"]\s*\]\s*=\s*\{")
    m = pattern.search(text)
    if not m:
        return None
    brace = text.find("{", m.start())
    return _balanced_brace_block(text, brace)


def guild_shop_names(text: str) -> tuple[str, ...]:
    names = re.findall(r"\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=\s*\{", text)
    # The file can contain nested string-keyed tables; retain only blocks that look
    # like guild-shop definitions.
    result = []
    for name in names:
        block = _named_table_block(text, name)
        if block and re.search(r"\b(?:stock|sharedStock|hours|holiday)\s*=", block):
            result.append(name)
    return tuple(dict.fromkeys(result))


def parse_guild_shops_data(text: str, *, source_path: str = "scripts/data/guild_shops.lua") -> dict[str, Any]:
    """Parse static modern LSB guild-shop definitions.

    sharedStock aliases are retained as shop records with no copied inventory; their
    alias target is metadata so callers can resolve it explicitly.
    """
    shops: list[ShopRecord] = []
    warnings: list[str] = []

    for name in guild_shop_names(text):
        block = _named_table_block(text, name)
        if not block:
            continue
        shared = re.search(r"\bsharedStock\s*=\s*['\"]([^'\"]+)['\"]", block)
        if shared:
            shops.append(ShopRecord(
                shop_id=f"guild-shop:{name}",
                shop_kind="GUILD",
                vendor_name=name,
                source_path=source_path,
                source_family="LSB",
                items=(),
                metadata={"shared_stock": shared.group(1), "source_scope": "DATA"},
            ))
            continue

        stock_match = re.search(r"\bstock\s*=\s*\{", block)
        if not stock_match:
            warnings.append(f"{name}: no stock/sharedStock field")
            continue
        stock_start = block.find("{", stock_match.start())
        stock = _balanced_brace_block(block, stock_start)
        if not stock:
            warnings.append(f"{name}: malformed stock table")
            continue

        items: list[ShopItem] = []
        row_re = re.compile(r"\{([^{}]+)\}")
        for row in row_re.findall(stock):
            item_m = re.search(rf"\bid\s*=\s*({_ITEM_EXPR})", row)
            if not item_m:
                continue
            def field_int(field: str) -> int | None:
                m = re.search(rf"\b{re.escape(field)}\s*=\s*(\d+)", row)
                return int(m.group(1)) if m else None
            metadata = {
                key: value
                for key in ("initial", "maxStock", "targetStock", "buyMax", "restockRate")
                if (value := field_int(key)) is not None
            }
            for flag in ("hidden", "noSell"):
                m = re.search(rf"\b{flag}\s*=\s*(true|false)", row)
                if m:
                    metadata[flag] = m.group(1) == "true"
            items.append(ShopItem(
                item_m.group(1),
                metadata.get("buyMax"),
                metadata,
            ))

        shops.append(ShopRecord(
            shop_id=f"guild-shop:{name}",
            shop_kind="GUILD",
            vendor_name=name,
            source_path=source_path,
            source_family="LSB",
            items=tuple(items),
            metadata={"static_stock": True, "source_scope": "DATA"},
        ))

    return {
        "status": "OK" if shops else "UNSUPPORTED",
        "source_path": source_path,
        "shops": tuple(shops),
        "warnings": tuple(warnings),
    }


def numeric_item_id(item_literal: str) -> int | None:
    """Return a numeric item literal when the source used one directly."""
    try:
        return int(str(item_literal), 0)
    except (TypeError, ValueError):
        return None

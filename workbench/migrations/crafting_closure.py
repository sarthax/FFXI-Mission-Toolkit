"""Recursive synthesis/synergy prerequisite closure.

This module answers a narrow but important question:
"If we choose a crafting acquisition path for an item, what must exist for that
path to succeed?"

It deliberately does not guess that leaf materials are obtainable. A leaf item
with no known recipe/acquisition evidence remains unresolved until another
acquisition analyzer (shop/drop/reward/etc.) satisfies it.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Iterable

from workbench.adapters.servers.base import LogicalRecord


CRAFT_FIELDS = (
    "woodworking",
    "smithing",
    "goldsmithing",
    "clothcraft",
    "leathercraft",
    "bonecraft",
    "alchemy",
    "cooking",
)

INGREDIENT_FIELDS = tuple(f"ingredient_{i}" for i in range(1, 9))


@dataclass(frozen=True)
class CraftPath:
    path_id: str
    system: str
    recipe_id: int | str
    result_item_id: int
    result_name: str | None
    ingredient_item_ids: tuple[int, ...]
    crystal_item_id: int | None
    key_item_id: int | None
    craft_requirements: tuple[tuple[str, int], ...]
    system_requirements: tuple[str, ...]
    source_family: str
    source_table: str


def _int(value):
    if value in (None, "", 0, "0"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def craft_path_from_record(record: LogicalRecord) -> CraftPath:
    fields = record.fields
    result = _int(fields.get("result_item_id"))
    if result is None:
        raise ValueError("Recipe record has no result_item_id")

    ingredients = tuple(
        item
        for item in (_int(fields.get(name)) for name in INGREDIENT_FIELDS)
        if item is not None
    )

    recipe_id = dict(record.identity).get("recipe_id")
    if recipe_id is None:
        recipe_id = fields.get("recipe_id")

    if record.logical_type == "synth_recipes":
        crafts = tuple(
            (name, int(value))
            for name in CRAFT_FIELDS
            if (value := _int(fields.get(name))) is not None
        )
        return CraftPath(
            path_id=f"synthesis:{recipe_id}",
            system="SYNTHESIS",
            recipe_id=recipe_id,
            result_item_id=result,
            result_name=fields.get("result_name"),
            ingredient_item_ids=ingredients,
            crystal_item_id=_int(fields.get("crystal_item_id")),
            key_item_id=_int(fields.get("key_item_id")),
            craft_requirements=crafts,
            system_requirements=("SYNTHESIS_RUNTIME",),
            source_family=record.source_family,
            source_table=record.source_table,
        )

    if record.logical_type == "synergy_recipes":
        skills = []
        for prefix in ("primary", "secondary", "tertiary"):
            skill = _int(fields.get(f"{prefix}_skill"))
            rank = _int(fields.get(f"{prefix}_rank"))
            if skill is not None:
                skills.append((f"skill:{skill}", rank or 0))
        return CraftPath(
            path_id=f"synergy:{recipe_id}",
            system="SYNERGY",
            recipe_id=recipe_id,
            result_item_id=result,
            result_name=fields.get("result_name"),
            ingredient_item_ids=ingredients,
            crystal_item_id=None,
            key_item_id=None,
            craft_requirements=tuple(skills),
            system_requirements=("SYNERGY_RUNTIME", "SYNERGY_CLIENT_CAPABILITY"),
            source_family=record.source_family,
            source_table=record.source_table,
        )

    raise ValueError(f"Unsupported recipe logical type: {record.logical_type}")


def index_craft_paths(records: Iterable[LogicalRecord]) -> dict[int, list[CraftPath]]:
    by_result: dict[int, list[CraftPath]] = defaultdict(list)
    for record in records:
        if record.logical_type not in {"synth_recipes", "synergy_recipes"}:
            continue
        path = craft_path_from_record(record)
        by_result[path.result_item_id].append(path)
    return dict(by_result)


def build_crafting_closure(
    records: Iterable[LogicalRecord],
    result_item_id: int,
    *,
    known_obtainable_items: Iterable[int] = (),
    available_systems: Iterable[str] = ("SYNTHESIS_RUNTIME",),
    known_key_items: Iterable[int] = (),
    max_depth: int = 12,
) -> dict:
    """Build an OR-graph for crafting paths to one item.

    A result item is craft-viable when at least one recipe path is viable.
    A recipe path is viable only when:
      - its required crafting system/capability is available;
      - its key item is available when required;
      - every ingredient and crystal is either independently obtainable or has
        at least one recursively viable crafting path.

    Items with no known path and not explicitly known obtainable are unresolved.
    """
    if max_depth < 1 or max_depth > 32:
        raise ValueError("max_depth must be between 1 and 32")

    by_result = index_craft_paths(records)
    obtainable = {int(x) for x in known_obtainable_items}
    systems = {str(x) for x in available_systems}
    key_items = {int(x) for x in known_key_items}

    memo: dict[tuple[int, int], dict] = {}

    def visit(item_id: int, depth: int, stack: tuple[int, ...]) -> dict:
        key = (item_id, depth)
        if key in memo:
            return memo[key]

        if item_id in obtainable:
            result = {
                "item_id": item_id,
                "status": "OBTAINABLE",
                "satisfied_by": "EXTERNAL_ACQUISITION",
                "paths": [],
                "unresolved": [],
            }
            memo[key] = result
            return result

        if item_id in stack:
            return {
                "item_id": item_id,
                "status": "BLOCKED",
                "satisfied_by": None,
                "paths": [],
                "unresolved": [f"crafting cycle detected at item {item_id}"],
            }

        if depth >= max_depth:
            return {
                "item_id": item_id,
                "status": "BLOCKED",
                "satisfied_by": None,
                "paths": [],
                "unresolved": [f"maximum crafting depth {max_depth} reached"],
            }

        paths = []
        viable_count = 0
        unresolved_messages = []
        for path in by_result.get(item_id, []):
            missing_systems = [req for req in path.system_requirements if req not in systems]
            key_item_ok = path.key_item_id is None or path.key_item_id in key_items

            ingredient_nodes = []
            ingredient_ok = True
            for ingredient in path.ingredient_item_ids:
                node = visit(ingredient, depth + 1, stack + (item_id,))
                ingredient_nodes.append(node)
                if node["status"] != "OBTAINABLE":
                    ingredient_ok = False

            crystal_node = None
            if path.crystal_item_id is not None:
                crystal_node = visit(path.crystal_item_id, depth + 1, stack + (item_id,))
                if crystal_node["status"] != "OBTAINABLE":
                    ingredient_ok = False

            reasons = []
            if missing_systems:
                reasons.append("missing systems: " + ", ".join(missing_systems))
            if not key_item_ok:
                reasons.append(f"missing required key item {path.key_item_id}")
            for node in ingredient_nodes:
                if node["status"] != "OBTAINABLE":
                    reasons.append(f"ingredient {node['item_id']} unresolved")
            if crystal_node and crystal_node["status"] != "OBTAINABLE":
                reasons.append(f"crystal {crystal_node['item_id']} unresolved")

            path_viable = not missing_systems and key_item_ok and ingredient_ok
            if path_viable:
                viable_count += 1

            path_row = {
                **asdict(path),
                "status": "VIABLE" if path_viable else "UNRESOLVED",
                "missing_systems": missing_systems,
                "key_item_available": key_item_ok,
                "ingredients": ingredient_nodes,
                "crystal": crystal_node,
                "reasons": reasons,
            }
            paths.append(path_row)
            unresolved_messages.extend(reasons)

        if viable_count:
            status = "OBTAINABLE"
            satisfied_by = "CRAFTING"
        elif paths:
            status = "UNRESOLVED"
            satisfied_by = None
        else:
            status = "UNRESOLVED"
            satisfied_by = None
            unresolved_messages.append(
                f"item {item_id} has no known crafting path and no verified alternate acquisition"
            )

        result = {
            "item_id": item_id,
            "status": status,
            "satisfied_by": satisfied_by,
            "paths": paths,
            "unresolved": sorted(set(unresolved_messages)),
        }
        memo[key] = result
        return result

    root = visit(int(result_item_id), 0, ())
    return {
        "schema": 1,
        "kind": "WORKBENCH_CRAFTING_CLOSURE",
        "result_item_id": int(result_item_id),
        "status": root["status"],
        "root": root,
        "available_systems": sorted(systems),
        "known_key_items": sorted(key_items),
        "known_obtainable_items": sorted(obtainable),
        "notes": [
            "Crafting closure is an OR-graph: one viable acquisition path is sufficient.",
            "Selecting a crafting path recursively requires every ingredient/crystal prerequisite on that path.",
            "Leaf items are not assumed obtainable; another acquisition analyzer must prove them.",
            "Synergy is modeled as a distinct server/client capability from ordinary synthesis.",
        ],
    }

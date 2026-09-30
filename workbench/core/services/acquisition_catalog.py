"""Source-neutral acquisition catalog over audited Workbench producers.

This module normalizes acquisition evidence without inventing cross-source canonical
identity.  Item/key-item literals remain literals until an explicit identity bridge
maps them to canonical graph nodes.

Supported producer families in v1:
- mob_drops logical SQL records -> DROP_POOL
- synth_recipes logical SQL records -> SYNTHESIS
- synergy_recipes logical SQL records -> SYNERGY
- scripted-behavior reward projections -> SCRIPTED_REWARD

Shop acquisition is intentionally absent until an audited logical shop profile exists.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from hashlib import sha1
from typing import Any, Iterable

from workbench.adapters.servers.base import LogicalRecord
from workbench.adapters.servers.shop_lua import ShopRecord, numeric_item_id


SCHEMA_VERSION = "acquisition-catalog/v1"
SUPPORTED_ACQUISITION_TYPES = (
    "DROP_POOL",
    "SOLD_BY",
    "SYNTHESIS",
    "SYNERGY",
    "SCRIPTED_REWARD",
)


@dataclass(frozen=True)
class AcquisitionPath:
    path_id: str
    subject_kind: str
    subject_id: str
    acquisition_type: str
    source_family: str
    source_table: str
    source_identity: tuple[tuple[str, Any], ...]
    source_label: str | None = None
    metadata: dict[str, Any] | None = None
    confidence: str = "VERIFIED"
    evidence_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["source_identity"] = [list(x) for x in self.source_identity]
        row["evidence_ids"] = list(self.evidence_ids)
        row["metadata"] = dict(self.metadata or {})
        return row


def _token(*parts: object) -> str:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


def _value(fields: dict[str, Any], name: str) -> str | None:
    value = fields.get(name)
    if value in (None, "", 0, "0"):
        return None
    return str(value)


def _recipe_path(record: LogicalRecord) -> AcquisitionPath | None:
    result = _value(record.fields, "result_item_id")
    if result is None:
        return None
    recipe_id = dict(record.identity).get("recipe_id")
    if recipe_id is None:
        recipe_id = record.fields.get("recipe_id")
    acquisition_type = "SYNTHESIS" if record.logical_type == "synth_recipes" else "SYNERGY"
    ingredients = [
        str(record.fields[name])
        for name in (f"ingredient_{i}" for i in range(1, 9))
        if record.fields.get(name) not in (None, "", 0, "0")
    ]
    metadata = {
        "recipe_id": recipe_id,
        "result_name": record.fields.get("result_name"),
        "result_qty": record.fields.get("result_qty"),
        "ingredient_item_ids": ingredients,
    }
    if acquisition_type == "SYNTHESIS":
        metadata.update({
            "crystal_item_id": record.fields.get("crystal_item_id"),
            "key_item_id": record.fields.get("key_item_id"),
            "craft_levels": {
                name: record.fields.get(name)
                for name in (
                    "woodworking", "smithing", "goldsmithing", "clothcraft",
                    "leathercraft", "bonecraft", "alchemy", "cooking",
                )
                if record.fields.get(name) not in (None, "", 0, "0")
            },
        })
    else:
        metadata["skills"] = [
            {
                "skill": record.fields.get(f"{prefix}_skill"),
                "rank": record.fields.get(f"{prefix}_rank"),
            }
            for prefix in ("primary", "secondary", "tertiary")
            if record.fields.get(f"{prefix}_skill") not in (None, "", 0, "0")
        ]
    return AcquisitionPath(
        path_id=f"acquisition:{acquisition_type.lower()}:{_token(record.source_family, recipe_id, result)}",
        subject_kind="ITEM",
        subject_id=result,
        acquisition_type=acquisition_type,
        source_family=record.source_family,
        source_table=record.source_table,
        source_identity=record.identity,
        source_label=record.fields.get("result_name"),
        metadata=metadata,
    )


def _drop_path(record: LogicalRecord) -> AcquisitionPath | None:
    item = _value(record.fields, "item_id")
    if item is None:
        return None
    drop_id = record.fields.get("drop_id")
    metadata = {
        "drop_id": drop_id,
        "drop_type": record.fields.get("drop_type"),
        "group_id": record.fields.get("group_id"),
        "group_rate": record.fields.get("group_rate"),
        "item_rate": record.fields.get("item_rate"),
    }
    return AcquisitionPath(
        path_id=f"acquisition:drop:{_token(record.source_family, record.identity, item)}",
        subject_kind="ITEM",
        subject_id=item,
        acquisition_type="DROP_POOL",
        source_family=record.source_family,
        source_table=record.source_table,
        source_identity=record.identity,
        source_label=f"drop_id {drop_id}" if drop_id is not None else "drop pool",
        metadata=metadata,
    )


def acquisition_paths_from_logical_records(
    records: Iterable[LogicalRecord],
) -> tuple[AcquisitionPath, ...]:
    """Normalize audited logical SQL records into acquisition paths."""
    paths: list[AcquisitionPath] = []
    for record in records:
        path = None
        if record.logical_type == "mob_drops":
            path = _drop_path(record)
        elif record.logical_type in {"synth_recipes", "synergy_recipes"}:
            path = _recipe_path(record)
        if path is not None:
            paths.append(path)
    return tuple(sorted(paths, key=lambda row: (row.subject_kind, row.subject_id, row.acquisition_type, row.path_id)))


def acquisition_paths_from_scripted_projection(projection: Any) -> tuple[AcquisitionPath, ...]:
    """Adapt existing scripted-behavior reward evidence without changing graph IDs.

    The function consumes the public projection shape (entities + edges) by metadata,
    so the acquisition catalog remains independent of scripted-behavior internals.
    """
    entities = {entity.entity_id: entity for entity in getattr(projection, "entities", ())}
    paths: list[AcquisitionPath] = []
    for edge in getattr(projection, "edges", ()):
        if getattr(edge, "relationship", None) != "REWARDED_BY":
            continue
        entity = entities.get(edge.source_node)
        metadata = dict(getattr(entity, "metadata", {}) or {}) if entity is not None else {}
        source_effect = str(metadata.get("source_effect") or "")
        literal = metadata.get("source_value")
        if literal in (None, ""):
            continue
        subject_kind = "KEY_ITEM" if source_effect == "GRANT_KEY_ITEM" else "ITEM"
        notes = getattr(edge, "notes", None)
        edge_metadata = dict(notes or {}) if isinstance(notes, dict) else {}
        evidence_id = getattr(edge, "evidence_id", None)
        paths.append(AcquisitionPath(
            path_id=f"acquisition:scripted-reward:{_token(edge.edge_id, literal)}",
            subject_kind=subject_kind,
            subject_id=str(literal),
            acquisition_type="SCRIPTED_REWARD",
            source_family="SCRIPTED_BEHAVIOR",
            source_table="behavior_projection",
            source_identity=(("reward_edge_id", edge.edge_id),),
            source_label=getattr(entity, "display_name", None) if entity is not None else str(literal),
            metadata={
                "reward_node": edge.source_node,
                "reward_source_node": edge.target_node,
                "source_effect": source_effect,
                "identity_status": metadata.get("identity_status"),
                "edge_metadata": edge_metadata,
            },
            confidence=getattr(edge, "confidence", None) or "UNKNOWN",
            evidence_ids=(str(evidence_id),) if evidence_id else (),
        ))
    return tuple(sorted(paths, key=lambda row: (row.subject_kind, row.subject_id, row.path_id)))




def acquisition_paths_from_shops(
    shops: Iterable[ShopRecord],
) -> tuple[AcquisitionPath, ...]:
    """Normalize audited static Lua shop inventories into SOLD_BY paths."""
    paths: list[AcquisitionPath] = []
    for shop in shops:
        for index, item in enumerate(shop.items):
            metadata = {
                "shop_id": shop.shop_id,
                "shop_kind": shop.shop_kind,
                "vendor_name": shop.vendor_name,
                "price": item.price,
                "item_literal": item.item_literal,
                "item_numeric_id": numeric_item_id(item.item_literal),
                "shop_metadata": dict(shop.metadata or {}),
                "item_metadata": dict(item.metadata or {}),
            }
            paths.append(AcquisitionPath(
                path_id=f"acquisition:sold-by:{_token(shop.shop_id, item.item_literal, index)}",
                subject_kind="ITEM",
                subject_id=str(item.item_literal),
                acquisition_type="SOLD_BY",
                source_family="LSB_LUA_SHOP",
                source_table=shop.shop_kind,
                source_identity=(("shop_id", shop.shop_id), ("item_literal", item.item_literal)),
                source_label=shop.vendor_name,
                metadata=metadata,
                confidence="VERIFIED",
            ))
    return tuple(sorted(paths, key=lambda row: (row.subject_id, row.path_id)))

def build_acquisition_catalog(
    *,
    logical_records: Iterable[LogicalRecord] = (),
    scripted_projections: Iterable[Any] = (),
    shops: Iterable[ShopRecord] = (),
) -> dict[str, Any]:
    """Build a deterministic acquisition catalog grouped by literal subject identity."""
    paths = list(acquisition_paths_from_logical_records(logical_records))
    for projection in scripted_projections:
        paths.extend(acquisition_paths_from_scripted_projection(projection))
    paths.extend(acquisition_paths_from_shops(shops))
    paths.sort(key=lambda row: (row.subject_kind, row.subject_id, row.acquisition_type, row.path_id))

    grouped: dict[tuple[str, str], list[AcquisitionPath]] = defaultdict(list)
    for path in paths:
        grouped[(path.subject_kind, path.subject_id)].append(path)

    subjects = []
    for (kind, subject_id), rows in sorted(grouped.items()):
        subjects.append({
            "subject_kind": kind,
            "subject_id": subject_id,
            "acquisition_types": sorted({row.acquisition_type for row in rows}),
            "paths": [row.as_dict() for row in rows],
        })

    counts = defaultdict(int)
    for path in paths:
        counts[path.acquisition_type] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "supported_acquisition_types": list(SUPPORTED_ACQUISITION_TYPES),
        "unsupported_until_profiled": ["CURIO_VENDOR", "SPECIAL_DYNAMIC_SHOP"],
        "subject_count": len(subjects),
        "path_count": len(paths),
        "counts": dict(sorted(counts.items())),
        "subjects": subjects,
        "notes": [
            "Acquisition identities remain source literals until an explicit identity bridge maps them.",
            "Multiple acquisition paths are alternatives; presence of one path does not prove runtime obtainability.",
            "SOLD_BY covers audited static general/nation/guild Lua shop inventories; special dynamic shop systems remain separate.",
        ],
    }


def verified_external_item_ids(catalog: dict[str, Any]) -> set[int]:
    """Return numeric ITEM literals with at least one VERIFIED non-crafting acquisition path.

    This is suitable as the external-acquisition input to crafting closure while keeping
    synthesis/synergy recursion inside the crafting engine itself.
    """
    result: set[int] = set()
    for subject in catalog.get("subjects", ()):
        if subject.get("subject_kind") != "ITEM":
            continue
        rows = subject.get("paths", ())
        if not any(
            row.get("confidence") == "VERIFIED"
            and row.get("acquisition_type") in {"DROP_POOL", "SOLD_BY", "SCRIPTED_REWARD"}
            for row in rows
        ):
            continue
        try:
            result.add(int(subject["subject_id"]))
        except (TypeError, ValueError):
            continue
    return result

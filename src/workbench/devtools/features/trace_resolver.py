"""Central query resolver for Feature Trace.

The resolver ranks indexed representations, groups obvious same-object identities, and chooses a
single trace root only when the evidence is strong enough.  It deliberately does not manufacture
canonical graph edges; ambiguous roots stay ambiguous and are returned to the caller.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Iterable


ENTITY_TYPES = {"NPC", "MOB", "INSTANCE_ENTITY", "CLIENT_IDENTITY", "ENTITY"}
MISSION_TYPES = {"MISSION", "QUEST", "ASSAULT_MISSION"}
ITEM_TYPES = {"ITEM", "ITEM_EQUIPMENT", "ITEM_WEAPON", "ITEM_USABLE", "KEY_ITEM", "KEY_ITEM_REFERENCE"}


@dataclass(frozen=True)
class Resolution:
    query: str
    status: str
    root: str | None
    object_kind: str
    confidence: str
    candidates: tuple[dict, ...]
    groups: tuple[dict, ...]
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "status": self.status,
            "root": self.root,
            "object_kind": self.object_kind,
            "confidence": self.confidence,
            "candidates": list(self.candidates),
            "groups": list(self.groups),
            "reasons": list(self.reasons),
        }


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _numeric_identity(row: dict) -> str | None:
    for source in (row, row.get("identity") or {}, row.get("aliases") or {}, row.get("details") or {}):
        for key in ("numeric_id", "npcid", "mobid", "entity_id", "itemid", "mission_id", "quest_id", "id"):
            value = source.get(key) if isinstance(source, dict) else None
            if value not in (None, ""):
                return str(value)
    return None


def object_kind(row: dict) -> str:
    node_type = str(row.get("node_type") or "").upper()
    if node_type in ENTITY_TYPES:
        return "entity"
    if node_type in MISSION_TYPES or "MISSION" in node_type or "QUEST" in node_type:
        return "mission"
    if node_type in ITEM_TYPES or "ITEM" in node_type:
        return "item"
    if node_type in {"INSTANCE", "BATTLEFIELD"}:
        return "instance"
    if node_type in {"SPELL", "ABILITY", "WEAPON_SKILL", "MOB_SKILL", "TRAIT"}:
        return "ability"
    if node_type in {"CAPTURE", "CLIENT_IDENTITY", "CLIENT_SNAPSHOT"}:
        return "runtime"
    if node_type in {"FUNCTION", "BINDING", "ARTIFACT", "BUILD_TARGET"}:
        return "implementation"
    return "feature"


def _candidate_score(query: str, row: dict) -> tuple[int, list[str]]:
    q = str(query or "").strip()
    qf = q.casefold()
    qn = _norm(q)
    node_id = str(row.get("node_id") or "")
    name = str(row.get("display_name") or "")
    numeric = _numeric_identity(row)
    score = 0
    reasons = []
    if node_id.casefold() == qf:
        score += 120; reasons.append("exact node id")
    if name.casefold() == qf and name:
        score += 110; reasons.append("exact display name")
    if numeric is not None and qf in {numeric.casefold(), f"npc:{numeric}".casefold(), f"mob:{numeric}".casefold(), f"entity:{numeric}".casefold()}:
        score += 105; reasons.append("exact numeric identity")
    if qn and _norm(name) == qn and name:
        score += 90; reasons.append("normalized name")
    if qn and qn in _norm(name) and name:
        score += 45; reasons.append("name contains query")
    if qf and qf in node_id.casefold():
        score += 35; reasons.append("node id contains query")
    matched = tuple(str(x) for x in row.get("matched_on") or ())
    if matched:
        score += min(25, 5 * len(matched)); reasons.append("indexed alias/detail match")
    provider = str(row.get("provider") or "")
    if provider and provider != "schema-fallback":
        score += 5
    return score, reasons


def _group_key(row: dict) -> tuple[str, str]:
    kind = object_kind(row)
    numeric = _numeric_identity(row)
    if numeric is not None and kind in {"entity", "item", "mission"}:
        return kind, numeric
    name = _norm(row.get("display_name"))
    return kind, name or str(row.get("node_id") or "")


def resolve_candidates(query: str, rows: Iterable[dict]) -> Resolution:
    ranked = []
    for row in rows:
        score, reasons = _candidate_score(query, row)
        item = dict(row)
        item["resolver_score"] = score
        item["resolver_reasons"] = reasons
        item["resolver_kind"] = object_kind(row)
        ranked.append(item)
    ranked.sort(key=lambda row: (-row["resolver_score"], str(row.get("display_name") or "").casefold(), str(row.get("node_id") or "")))

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in ranked:
        grouped[_group_key(row)].append(row)
    groups = []
    for (kind, identity), members in grouped.items():
        groups.append({
            "kind": kind,
            "identity": identity,
            "score": max((m["resolver_score"] for m in members), default=0),
            "representations": members,
            "node_ids": sorted({str(m.get("node_id") or "") for m in members}),
        })
    groups.sort(key=lambda group: (-group["score"], group["kind"], group["identity"]))

    if not ranked:
        return Resolution(query, "NOT_FOUND", None, "unknown", "NONE", tuple(), tuple(),
                          ("No indexed representation matched the query.",))
    best = ranked[0]
    second = ranked[1]["resolver_score"] if len(ranked) > 1 else -1
    best_score = best["resolver_score"]
    best_group = next((g for g in groups if best in g["representations"]), groups[0])
    # A strong exact match may select one representation; grouped aliases remain visible for expansion.
    if best_score >= 100 and (best_score - second >= 10 or len(best_group["representations"]) > 1):
        return Resolution(query, "RESOLVED", str(best.get("node_id")), best["resolver_kind"], "VERIFIED",
                          tuple(ranked), tuple(groups), tuple(best["resolver_reasons"]))
    if len(groups) == 1 and best_score >= 60:
        root = str(best.get("node_id"))
        return Resolution(query, "RESOLVED", root, best["resolver_kind"], "STRONG",
                          tuple(ranked), tuple(groups), tuple(best["resolver_reasons"]))
    return Resolution(query, "AMBIGUOUS", None, best["resolver_kind"], "REVIEW",
                      tuple(ranked), tuple(groups),
                      ("Multiple plausible feature roots remain; choose a representation or refine the query.",))

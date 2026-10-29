"""Read-only consumer for XIHeadless's canonical personality catalog v1.

Toolkit never owns the catalog, evaluates a rule, or controls a Headless bot.
The source bytes must be explicitly supplied and pinned to a reviewed Headless
Git blob SHA; no network, subprocess, live client or server calls.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping


CATALOG_ID = "xiheadless-personalities"
VERSION = "1.0.0"
SOURCE_REPO = "sarthax/xiheadless-dsp"
# Draft Headless PR #215 commit/blob: deliberately must be updated after review.
CANDIDATE_SOURCE_COMMIT = "a025dc71b64c1d7d79319d19159fdedcb5647c01"
CANDIDATE_SOURCE_GIT_BLOB = "b0166b818862b5b7996e0b0c3f6d8449240e4474"


@dataclass(frozen=True)
class CatalogPin:
    repository: str
    commit: str
    git_blob_sha1: str


CANDIDATE_PIN = CatalogPin(
    SOURCE_REPO, CANDIDATE_SOURCE_COMMIT, CANDIDATE_SOURCE_GIT_BLOB,
)


@dataclass(frozen=True)
class ReadOnlyCatalog:
    metadata: Mapping[str, Any]
    jobs: tuple[Mapping[str, Any], ...]
    profiles: tuple[Mapping[str, Any], ...]
    capabilities: tuple[Mapping[str, Any], ...]
    inspirations: tuple[Mapping[str, Any], ...]


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _blob_hash(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()


def load_pinned_manifest(raw: bytes, pin: CatalogPin = CANDIDATE_PIN) -> ReadOnlyCatalog:
    """Validate bytes and show design-only content; never run a profile."""
    _require(isinstance(raw, bytes) and 1 <= len(raw) <= 4_000_000,
             "a bounded Headless JSON byte payload is required")
    _require(isinstance(pin, CatalogPin) and pin.repository == SOURCE_REPO,
             "only the canonical Headless repository may supply data")
    _require(re.fullmatch(r"[a-f0-9]{40}", pin.commit) is not None and
             re.fullmatch(r"[a-f0-9]{40}", pin.git_blob_sha1) is not None,
             "source commit and blob pin must be exact SHAs")
    _require(_blob_hash(raw) == pin.git_blob_sha1,
             "catalog bytes do not match independently reviewed Headless git blob")
    try:
        catalog = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid UTF-8 JSON") from exc
    _require(isinstance(catalog, dict), "catalog must be object")
    expected = {
        "schema_version", "catalog_id", "authority", "consumers", "runtime_status",
        "source_revisions", "invariants", "capabilities", "profiles",
        "jobs", "trust_inspirations",
    }
    _require(set(catalog) == expected, "unrecognized or missing Headless catalog fields")
    _require(catalog["schema_version"] == VERSION and catalog["catalog_id"] == CATALOG_ID,
             "unsupported personality catalog version")
    _require(catalog["authority"] == "XIHEADLESS_CANONICAL_DATA" and
             catalog["runtime_status"] == "DESIGN_ONLY",
             "cannot import noncanonical or runtime-ready data")
    _require(catalog["consumers"] == {
        "primary": ["xiheadless", "mission_toolkit"],
        "secondary": ["valhalla_trust_adapter"],
    }, "Toolkit must remain a primary read-only consumer")
    _require(catalog["invariants"].get("no_execution") is True and
             catalog["invariants"].get("trust_adapter_target_restrictions") == "NOT_INHERITED",
             "catalog cannot grant execution or impose Valhalla owner-only targeting")

    lists = ("jobs", "profiles", "capabilities", "trust_inspirations")
    for k in lists:
        _require(isinstance(catalog[k], list), f"{k} must be an array")
    _require(len(catalog["jobs"]) == 22, "all 22 jobs required")
    _require(len(catalog["profiles"]) >= 15, "insufficient personality profile inventory")
    _require(len(catalog["trust_inspirations"]) == 19, "source inspirations changed; review required")
    _require(len({p.get("id") for p in catalog["profiles"]}) ==
             len(catalog["profiles"]), "duplicate profile ids")
    _require(len({j.get("job_code") for j in catalog["jobs"]}) ==
             22, "duplicate job codes")
    profile_ids = {p.get("id") for p in catalog["profiles"]}
    for p in catalog["profiles"]:
        _require(p.get("runtime_status") == "DESIGN_ONLY" and
                 p.get("unknown_policy") == "INHIBIT_AND_REPORT" and
                 p.get("action_authority") == "EXISTING_HEADLESS_ROUTINES_ONLY",
                 "no profile may claim execution, certainty, or a new combat executor")
    for j in catalog["jobs"]:
        _require(j.get("headless_job_runtime_status") == "NOT_TESTED" and
                 j.get("personality_assignment_status") == "DESIGN_OPTION_ONLY",
                 "job binding must remain a design suggestion")
        suggestions = j.get("suggested_profile_ids")
        _require(isinstance(suggestions, list) and suggestions and
                 all(isinstance(p, str) and p in profile_ids for p in suggestions),
                 "job contains unsupported profile reference")
    for capability in catalog["capabilities"]:
        _require(capability.get("evidence_status") == "REQUIRES_ACCEPTANCE",
                 "source presence is not runtime capability")
    for person in catalog["trust_inspirations"]:
        _require(person.get("evidence_type") == "SOURCE_DECLARATION_ONLY" and
                 person.get("runtime_status") == "NOT_TESTED",
                 "LSB source examples do not prove a personality runs")
        if person.get("source_completeness") == "sparse_stub":
            _require(person.get("profile_inspirations") == [],
                     "sparse Trusts cannot be assigned invented profiles")

    meta = {
        "catalog_id": CATALOG_ID, "schema_version": VERSION,
        "source_repository": pin.repository, "source_commit": pin.commit,
        "source_git_blob": pin.git_blob_sha1,
        "view_kind": "READ_ONLY_PERSONALITY_CATALOG",
        "gameplay_verdict": "NOT_TESTED",
        "execution_enabled": False,
        "source_review_status": "PINNED_SOURCE_BYTES_ONLY",
    }
    return ReadOnlyCatalog(
        metadata=meta,
        jobs=tuple(catalog["jobs"]),
        profiles=tuple(catalog["profiles"]),
        capabilities=tuple(catalog["capabilities"]),
        inspirations=tuple(catalog["trust_inspirations"]),
    )


def compare_profiles(catalog: ReadOnlyCatalog, profile_ids: list[str]) -> dict[str, Any]:
    """Simple comparison for future Toolkit UI; no runtime decisions."""
    _require(isinstance(catalog, ReadOnlyCatalog), "validated catalog required")
    _require(isinstance(profile_ids, list) and 1 <= len(profile_ids) <= 6 and
             len(set(profile_ids)) == len(profile_ids) and
             all(isinstance(pid, str) for pid in profile_ids),
             "must select 1–6 distinct profile IDs")
    lookup = {p["id"]: p for p in catalog.profiles}
    _require(all(pid in lookup for pid in profile_ids),
             "cannot compare unknown profile")
    result = []
    for pid in profile_ids:
        p = lookup[pid]
        needed = sorted({fid for rule in p["behavior_preferences"]
                         for fid in rule["requires_facts"]})
        result.append({
            "profile_id": pid,
            "axis": p["axis"],
            "role_affinity": list(p["role_affinity"]),
            "intent_rules": tuple({
                "rule_id": rule["rule_id"], "priority": rule["priority"],
                "target_selector": rule["target_selector"],
                "condition_id": rule["condition_id"],
                "action_intent": rule["action_intent"],
            } for rule in p["behavior_preferences"]),
            "required_fact_ids": needed,
            "evidence_state": "NOT_VERIFIED",
            "execution_enabled": False,
        })
    return {
        "source_commit": catalog.metadata["source_commit"],
        "schema_version": VERSION, "view_kind": "READ_ONLY_COMPARISON",
        "gameplay_verdict": "NOT_TESTED", "execution_enabled": False,
        "profiles": result,
    }


def list_job_profiles(catalog: ReadOnlyCatalog, job_code: str) -> dict[str, Any]:
    _require(isinstance(catalog, ReadOnlyCatalog), "validated catalog required")
    row = next((j for j in catalog.jobs if j["job_code"] == job_code), None)
    _require(row is not None, "unknown Headless job")
    return {
        "job_code": row["job_code"], "primary_role": row["primary_party_role"],
        "eligible_roles": list(row["eligible_party_roles"]),
        "profile_ids": list(row["suggested_profile_ids"]),
        "source_commit": catalog.metadata["source_commit"],
        "assignment_status": "DESIGN_OPTION_ONLY",
        "gameplay_verdict": "NOT_TESTED", "execution_enabled": False,
    }

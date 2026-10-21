"""Read-only correlation and oracle *readiness* for capture-to-scenario review.

The return value is a separate diagnostic envelope, not a canonical test spec.
It does not authenticate supplied local catalog snapshots, derive gameplay
requirements from captures, make runtime verdicts, or change reviewer decisions.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re

from workbench.captures.scenario_review_workflow import _check

_SHA = re.compile(r"^[a-f0-9]{40}$", re.I)
_HASH = re.compile(r"^[a-f0-9]{64}$", re.I)
_SUPPORTED = {"npc": "npc", "npc_name": "npc", "item": "item",
              "item_name": "item", "key_item": "keyitem",
              "zone": "zone", "event": "event", "dialog": "dialog"}
_CATALOG_KIND = {"npc", "item", "keyitem", "zone"}
_READBACKS = {
    "capture_events": ("Independent NPC/event handler state or server branch readback",
                       "Zone, entity, message/event namespace from local client and DSP catalogs"),
    "capture_eventview": ("Authoritative event/CSID outcome plus client dialog cross-check",
                          "Decoder/schema revision and typed MesNum context"),
    "capture_ki_events": ("Client held key-item state and independent persisted server key-item readback",),
    "capture_structured_records": ("Independent client item inventory and persisted server item state",),
    "capture_raw_packets": ("Attested packet-field decoder plus server-side receipt/state observation",),
}


def _path(value: object) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 240 or "\\" in value:
        return False
    p = PurePosixPath(value)
    return not p.is_absolute() and all(x not in ("..", ".", "") for x in p.parts)


def _match(a: object, b: object) -> bool:
    return a is not None and b is not None and type(a) is type(b) and a == b


def _key(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _observation_digest(draft: dict) -> str:
    # Includes original observed summaries and indexed evidence, excluding
    # reviewer edits. This is a *projection* fingerprint, not physical attestation.
    payload = {
        "capture_id": draft["capture_id"],
        "evidence_map": draft["evidence_map"],
        "steps": [{"id": s["step_id"], "lane": s["lane"],
                   "observation": s["observed_summary"],
                   "refs": s["evidence_refs"],
                   "bindings": [(b["kind"], b["observed_value"]) for b in s["bindings"]]}
                  for s in draft["steps"]],
    }
    return sha256(_key(payload).encode()).hexdigest()


def _snapshot_valid(data: dict) -> bool:
    return (isinstance(data, dict) and isinstance(data.get("choices"), list)
            and len(data["choices"]) <= 50 and
            isinstance(data.get("kind"), str) and
            data.get("binding_verified") is False and
            data.get("execution_enabled") is False)


def _row_id(row: dict, kind: str):
    return row.get("id") if kind in _CATALOG_KIND else row.get("value")


def _source_proof(row: dict, snapshot: dict, proof: dict, binding: dict) -> bool:
    """Syntactic integrity gate. Actual source bytes must be checked locally.

    Do not treat a single bounded substring search hit as full reconciliation.
    """
    sha = snapshot.get("source_revision")
    return (snapshot.get("completeness") == "attested_complete_scoped_export"
            and isinstance(sha, str) and bool(_HASH.fullmatch(sha))
            and isinstance(proof, dict) and proof.get("classification") == "independent_reconciliation"
            and proof.get("binding_id") == binding["binding_id"]
            and proof.get("source_revision") == sha
            and proof.get("source_kind") == snapshot["kind"]
            and _match(proof.get("observed_value"), binding["observed_value"])
            and _match(proof.get("source_id"), _row_id(row, snapshot["kind"]))
            and proof.get("source_path") == row.get("source_path")
            and _path(row.get("source_path"))
            and isinstance(proof.get("line"), int) and not isinstance(proof.get("line"), bool)
            and proof["line"] > 0
            and isinstance(proof.get("reconciliation_ref"), str)
            and len(proof["reconciliation_ref"].strip()) >= 8
            and isinstance(row.get("name"), str)
            and row.get("identity_status") in {"unreconciled_source_candidate", "scoped_index_record"}
            and row.get("binding_verified") is False)


def _choices_for_binding(binding: dict, snapshot: dict) -> tuple[list[dict], list[dict]]:
    """Return scoped numeric and name candidates, without casting namespaces."""
    kind = snapshot["kind"]
    observed = binding["observed_value"]
    alternatives = observed if isinstance(observed, list) else [observed]
    exact, weak = [], []
    scope_zone = binding.get("scope", {}).get("zone_db")
    for row in snapshot["choices"]:
        if not isinstance(row, dict) or row.get("kind") != kind:
            raise ValueError("catalog row kind mismatch")
        if row.get("binding_verified") is not False or row.get("execution_enabled") is not False:
            raise ValueError("catalog must not claim verified/executable bindings")
        identifier = _row_id(row, kind)
        zone = row.get("zone_db")
        if kind in {"event", "dialog"}:
            # For event/dialog, zone is mandatory and same typed value; a
            # bare event number is NOT a globally unique identity.
            if scope_zone is None or not _match(scope_zone, zone):
                continue
        elif zone is not None and scope_zone is not None and not _match(scope_zone, zone):
            continue
        if binding["kind"] in {"npc_name", "item_name"}:
            if any(isinstance(v, str) and isinstance(row.get("name"), str)
                   and v.casefold() == row["name"].casefold() for v in alternatives):
                weak.append(row)
        elif any(_match(identifier, v) for v in alternatives):
            exact.append(row)
        elif any(isinstance(v, str) and isinstance(row.get("name"), str)
                 and v.casefold() == row["name"].casefold() for v in alternatives):
            weak.append(row)
    return exact, weak


def _classify(binding: dict, snapshot: dict | None, proof: dict | None) -> dict:
    kind = binding["kind"]
    base = {
        "binding_id": binding["binding_id"], "kind": kind,
        "observed_value": deepcopy(binding["observed_value"]),
        "evidence_refs": deepcopy(binding["evidence_refs"]),
        "review_decision": deepcopy(binding["review"]),
        "classification": "UNRESOLVED", "source_candidates": [],
        "selected_source": None, "source_identity_verified": False,
        "source_revision": None, "reason": "No compatible catalog source supplied",
    }
    if kind not in _SUPPORTED or (kind in {"event", "dialog"} and snapshot is None):
        base.update(classification="UNSUPPORTED",
                    reason="Event/dialog namespace needs explicit zone-scoped index; packet/MesNum/name-only fields cannot be typed here")
        return base
    if snapshot is None:
        return base
    if not _snapshot_valid(snapshot) or snapshot["kind"] != _SUPPORTED[kind]:
        raise ValueError("unsupported or unsafe catalog snapshot")
    if len(_key(snapshot).encode()) > 65536:
        raise ValueError("catalog snapshot exceeds bound")
    base["source_revision"] = snapshot.get("source_revision")
    matched, names = _choices_for_binding(binding, snapshot)
    matches = matched + names
    base["source_candidates"] = deepcopy(matches[:50])
    if isinstance(binding["observed_value"], list) and len(binding["observed_value"]) > 1:
        base.update(classification="AMBIGUOUS", reason="Capture itself recorded conflicting alternatives")
    elif len(matched) > 1 or len(names) > 1:
        base.update(classification="AMBIGUOUS", reason="Multiple compatible catalog candidates; cannot select an arbitrary row")
    elif len(matched) == 1 and matched[0].get("duplicate_id_in_results"):
        base.update(classification="AMBIGUOUS", reason="Catalog search reports duplicate source identity")
    elif len(matched) == 1 and _source_proof(matched[0], snapshot, proof, binding):
        base.update(classification="EXACT",
                    selected_source=deepcopy(matched[0]),
                    reason="Uniquely pinned catalog record + separately supplied reconciliation reference; local rehash still required")
    elif matches:
        base.update(classification="INFERRED",
                    reason="Catalog candidate agrees by a recorded value/name, but namespace reconciliation or complete revision proof is absent")
    else:
        base.update(classification="UNRESOLVED",
                    reason="No matching record in supplied *bounded* catalog results; not proof of absence")
    # Exact SOURCE RECORD != verified cross-client gameplay identity.
    return base


def _oracle(entry: dict | None, step_id: str, catalog_revisions: set[str]) -> dict:
    result = {"readiness": "UNKNOWN", "expected_candidate": None,
              "normative_expected": None, "independent_source": None,
              "blockers": ["NO_INDEPENDENT_SOURCE_BACKED_ORACLE"]}
    if entry is None:
        return result
    if not isinstance(entry, dict) or entry.get("step_id") != step_id:
        raise ValueError("oracle must be scoped to this step")
    # Explicitly reject any supposed oracle copied from a capture row or
    # unsupported executable/authoritative claim. Keep sources separate.
    if entry.get("origin") != "independent_dsp_source" or entry.get("from_capture") is not False:
        raise ValueError("source candidate must be independent of capture observation")
    if entry.get("execution_enabled") is not False:
        raise ValueError("oracle evidence must be nonexecutable")
    if not isinstance(entry.get("path"), str) or not _path(entry["path"]) or not entry["path"].endswith((".lua", ".sql")):
        raise ValueError("invalid DSP source path")
    commit, digest = entry.get("dsp_commit"), entry.get("file_sha256")
    if not isinstance(commit, str) or not _SHA.fullmatch(commit) or not isinstance(digest, str) or not _HASH.fullmatch(digest):
        raise ValueError("source reference must pin DSP commit and file digest")
    if (type(entry.get("line")) is not int or entry["line"] < 1
            or not isinstance(entry.get("preconditions"), list)
            or not 1 <= len(entry["preconditions"]) <= 12
            or not all(isinstance(x, str) and x.strip() for x in entry["preconditions"])
            or not isinstance(entry.get("readback"), str)
            or not 1 <= len(entry["readback"].strip()) <= 300):
        raise ValueError("source must include exact line, branch preconditions and independent readback")
    expected = entry.get("expected_candidate")
    if expected is None or isinstance(expected, (dict, list)) or type(expected) not in (str, int, bool) or len(str(expected)) > 300:
        raise ValueError("cannot invent complex or null oracle value")
    blockers = ["SOURCE_BYTES_NOT_INDEPENDENTLY_REHASHED", "REVIEWER_ORACLE_APPROVAL_REQUIRED",
                "INDEPENDENT_READBACK_NOT_YET_OBSERVED"]
    if catalog_revisions and commit not in catalog_revisions:
        blockers.append("DSP_SOURCE_REVISION_MISMATCH")
        readiness = "REVISION_BLOCKED"
    else:
        readiness = "SOURCE_CANDIDATE_REVIEW_REQUIRED"
    return {
        "readiness": readiness, "expected_candidate": deepcopy(expected),
        "normative_expected": None,
        "independent_source": {k: deepcopy(entry[k]) for k in
            ("path", "line", "dsp_commit", "file_sha256", "preconditions", "readback")},
        "blockers": blockers,
    }


def _repeated(draft: dict, peers: list[dict], accepted: dict) -> list[dict]:
    """Variations across captures, never silently a gameplay regression."""
    changes = []
    originals = draft["steps"]
    seen_peer_ids = set()
    def revisions(s: dict, source: dict) -> set[tuple]:
        versions = set()
        for ref in s["evidence_refs"]:
            for locator in source["evidence_map"][ref]["source"].get("references", []):
                manifest = locator.get("source_manifest") or {}
                versions.add((locator.get("source_sha256"), manifest.get("parser_name"),
                              manifest.get("parser_version")))
        return versions
    for peer in peers:
        _check(peer)
        if peer["capture_id"] == draft["capture_id"] or peer["capture_id"] in seen_peer_ids:
            raise ValueError("duplicate capture ID in repeated observations")
        seen_peer_ids.add(peer["capture_id"])
        for left in originals:
            for right in peer["steps"]:
                if left["lane"] != right["lane"] or not _match(left["zone_db"], right["zone_db"]):
                    continue
                # Comparing 2 unrelated records in the same zone is unsafe.
                def npc(s):
                    vals = [b["observed_value"] for b in s["bindings"] if b["kind"] == "npc"]
                    return vals[0] if len(vals) == 1 and not isinstance(vals[0], list) else None
                if not _match(npc(left), npc(right)):
                    continue
                kinds = ("event", "dialog", "key_item", "item")
                for kind in kinds:
                    a = [b["observed_value"] for b in left["bindings"] if b["kind"] == kind]
                    b = [bb["observed_value"] for bb in right["bindings"] if bb["kind"] == kind]
                    if len(a) != 1 or len(b) != 1 or _match(a[0], b[0]):
                        continue
                    # Even exact reconciled current identity does not verify the
                    # peer revision or precondition: report variation only.
                    changes.append({
                        "kind": "REPEATED_CAPTURE_VARIATION_NOT_PROVEN_CONTRADICTION",
                        "capture_ids": [draft["capture_id"], peer["capture_id"]],
                        "step_ids": [left["step_id"], right["step_id"]],
                        "field": kind, "recorded_values": [deepcopy(a[0]), deepcopy(b[0])],
                        "evidence_refs": [list(left["evidence_refs"]), list(right["evidence_refs"])],
                        "scope": {"zone_db": left["zone_db"], "npc_recorded_id": npc(left)},
                        "comparability": (
                            "SOURCE_OR_PARSER_REVISION_DIFFERENT"
                            if revisions(left, draft) != revisions(right, peer)
                            else "SOURCE_REVISIONS_INDEXED_PRECONDITIONS_NOT_ESTABLISHED"
                        ),
                    })
                    if len(changes) >= 100:
                        return changes
    return changes


def assess_evidence_readiness(draft: dict, *, catalog_snapshots: dict | None = None,
                               reconciliations: list[dict] | None = None,
                               independent_oracles: list[dict] | None = None,
                               comparison_drafts: list[dict] | None = None) -> dict:
    """Strictly noncanonical, synthetic/locally configured read-only diagnostics.

    Catalog snapshots are obtained separately from existing Toolkit providers;
    a bounded provider query can NEVER by itself establish a complete/exact
    binding. External reconciliation/source pointers are *claims* that the
    operator must validate against physical source bytes and pinned revisions.
    """
    _check(draft)
    catalogs = catalog_snapshots or {}
    proofs = reconciliations or []
    oracle_rows = independent_oracles or []
    peers = comparison_drafts or []
    if (not isinstance(catalogs, dict) or len(catalogs) > 500
            or not isinstance(proofs, list) or len(proofs) > 500
            or not isinstance(oracle_rows, list) or len(oracle_rows) > 100
            or not isinstance(peers, list) or len(peers) > 10):
        raise ValueError("unbounded readiness inputs")
    if len({_key(x.get("binding_id")) for x in proofs if isinstance(x, dict)}) != len(proofs):
        raise ValueError("duplicate reconciliation key")
    if len({_key(x.get("step_id")) for x in oracle_rows if isinstance(x, dict)}) != len(oracle_rows):
        raise ValueError("duplicate source-oracle step key")
    proof_by_id = {x["binding_id"]: x for x in proofs if isinstance(x, dict) and "binding_id" in x}
    oracle_by_id = {x["step_id"]: x for x in oracle_rows if isinstance(x, dict) and "step_id" in x}
    bindings = {b["binding_id"] for s in draft["steps"] for b in s["bindings"]}
    steps = {s["step_id"] for s in draft["steps"]}
    if (len(proof_by_id) != len(proofs) or len(oracle_by_id) != len(oracle_rows)
            or len(bindings) != sum(len(s["bindings"]) for s in draft["steps"])
            or set(catalogs) - bindings or set(proof_by_id) - bindings
            or set(oracle_by_id) - steps):
        raise ValueError("unknown or duplicated evidence reference in correlation input")
    results = []
    for s in draft["steps"]:
        ids = [_classify(b, catalogs.get(b["binding_id"]), proof_by_id.get(b["binding_id"]))
               for b in s["bindings"]]
        revisions = {x.get("dsp_commit") for x in catalogs.values()
                     if isinstance(x, dict) and isinstance(x.get("dsp_commit"), str)}
        oracle = _oracle(oracle_by_id.get(s["step_id"]), s["step_id"], revisions)
        missing = list(_READBACKS.get(s["lane"], ("Unsupported capture evidence family",)))
        if not s["evidence_refs"]:
            missing.append("Missing capture source-row references")
        for ref in s["evidence_refs"]:
            row = draft["evidence_map"][ref]
            if row["source"]["status"] not in ("LOCATED_SOURCE_SPAN", "FILE_LEVEL_ONLY"):
                missing.append("Ambiguous, unavailable or unverifiable original source-file locator")
            if row["source"].get("references"):
                for source in row["source"]["references"]:
                    manifest = source.get("source_manifest")
                    if not manifest or not manifest.get("parser_version"):
                        missing.append("Parser revision missing or not pinned")
        if any(x["classification"] != "EXACT" for x in ids if x["kind"] in _SUPPORTED):
            missing.append("Authoritative zone/identity namespace reconciliation still required")
        missing.extend(oracle["blockers"])
        missing.extend(s["review_gaps"])
        results.append({
            "step_id": s["step_id"], "observed": s["observed_summary"],
            "capture_evidence_refs": deepcopy(s["evidence_refs"]),
            "identity_candidates": ids, "oracle": oracle,
            "missing_observations_or_review": sorted(set(missing)),
            "reviewer_step_decision": deepcopy(s.get("review", {"decision": "PENDING"})),
            "normative_expected": None, "verdict": "UNKNOWN",
            "execution_enabled": False,
        })
    variations = _repeated(draft, peers, {})
    return {
        "contract": "capture_identity_oracle_readiness_v0_DIAGNOSTIC_ONLY",
        "capture_id": draft["capture_id"], "capture_projection_sha256": _observation_digest(draft),
        "classification": "OBSERVED_PLUS_INDEPENDENT_CANDIDATES",
        "steps": results, "repeated_capture_variations": variations,
        "source_integrity": "INDEXED_HASHES_ONLY_NOT_REHASHED",
        "oracle_review": "REQUIRED", "schema_compatibility": {
            "accepted": "canonical_v1_optional_BDD",
            "candidate_future_contract": "UNACCEPTED_DO_NOT_PROJECT",
            "automatic_import": False,
        },
        "execution_enabled": False, "approved_for_execution": False,
        "normative_expected": None, "verdict": "UNKNOWN",
    }


def candidate_dsp_catalogs(draft: dict, configured_dsp_root, *, limit: int = 20) -> dict:
    """Reuse Toolkit's existing read-only DSP lookup, not a new index/parser.

    All results are bounded, source-unpinned *candidates*. Operators may later
    attach source pins and independent reconciliation separately; nothing here
    can return EXACT. Dialog/event indices require distinct client/DSP context.
    """
    _check(draft)
    from workbench.server_admin.scenario_authoring.catalog_adapter import search_catalog
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("catalog limit must be 1..50")
    result = {}
    for s in draft["steps"]:
        for binding in s["bindings"]:
            kind = _SUPPORTED.get(binding["kind"])
            value = binding["observed_value"]
            if kind not in _CATALOG_KIND or isinstance(value, (list, dict)) or value is None:
                continue
            text = str(value)
            if len(text) > 64:
                continue
            result[binding["binding_id"]] = search_catalog(configured_dsp_root, kind, text, limit=limit)
    return result
